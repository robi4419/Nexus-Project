# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: jobs
# MAGIC
# MAGIC Rebuilds the job tables in `<catalog>.silver` from every landed file in the bronze job tables. All tables are
# MAGIC replaced on every run.
# MAGIC
# MAGIC 1. **Observations:** one row per job per run, with each source's fields renamed to one shared set of columns
# MAGIC    (only Jobicy for now; another source adds its own conform `SELECT` and a `UNION ALL`).
# MAGIC 2. **History:** when each job was first and last seen, in how many runs, and whether the latest run still lists it.
# MAGIC 3. **`silver.jobs`:** the latest version of each job, with plain-text description, seniority and salary in
# MAGIC    yearly USD (as-of join to `silver.fx_rates`).
# MAGIC 4. **Bridge tables:** `silver.job_industries`, `silver.job_types` and `silver.job_locations`.
# MAGIC
# MAGIC Parameters: `catalog` (e.g. `workspace`) and `bundle_root` (the bundle's files folder; when empty, the repo root
# MAGIC two folders above this notebook is used).

# COMMAND ----------

import os
import sys

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bundle_root", "")

catalog = dbutils.widgets.get("catalog")
bundle_root = dbutils.widgets.get("bundle_root") or os.path.abspath("../..")

# The bundle uploads the repo's transform/ package next to databricks/; make it importable.
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

print(f"Building {catalog}.silver job tables, using transform/ from {bundle_root}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Python functions for SQL
# MAGIC
# MAGIC `clean_html(html)` and `derive_seniority(title, source_level)` wrap the tested functions in `transform/`, so the
# MAGIC SQL below can call them like built-in functions. `derive_seniority` returns a struct: read its fields with
# MAGIC `.seniority` and `.seniority_source`.

# COMMAND ----------

from pyspark import cloudpickle
from pyspark.sql.types import StringType, StructField, StructType

import transform
from transform.seniority import seniority
from transform.text import html_to_text

# Spark runs Python functions on worker processes that don't have our sys.path change, so `import transform` would
# fail there. Pickling the package "by value" sends its code along with each function instead of just its name.
cloudpickle.register_pickle_by_value(transform)

SENIORITY_TYPE = StructType(
    [
        StructField("seniority", StringType()),
        StructField("seniority_source", StringType()),
    ]
)


def derive_seniority(title, source_level):
    level, source = seniority(title, source_level)
    return {"seniority": level, "seniority_source": source}


spark.udf.register("clean_html", html_to_text, StringType())
spark.udf.register("derive_seniority", derive_seniority, SENIORITY_TYPE)

# A quick self-test that runs both functions on the workers, not only here on the driver.
display(spark.sql("""
    SELECT clean_html('<p>Python &amp; SQL</p><ul><li>dbt</li></ul>') AS cleaned,
           derive_seniority('Sr. Data Engineer', 'Any') AS from_title,
           derive_seniority('Data Analyst', 'Midweight') AS from_source_level
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Observations
# MAGIC
# MAGIC Temp view `observations`: one row per job per landed file, columns `source`, `source_job_id`, `run_id`,
# MAGIC `landed_at`, `url`, `title`, `company_name`, `company_logo_url`, `published_at`, `level_raw`, `geo_raw`,
# MAGIC `industries`, `job_types`, `excerpt`, `description_html`, `salary_min`, `salary_max`, `salary_currency`,
# MAGIC `salary_period`.

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW observations AS
    WITH jobicy_job_variants AS (
        SELECT run_id, landed_at, EXPLODE(cast(body:jobs AS ARRAY<VARIANT>)) AS job
        FROM {catalog}.bronze.jobicy_raw
    )
    SELECT 
        'jobicy' AS source,
        job:id::STRING AS source_job_id,
        run_id, landed_at,
        job:url::STRING AS url,
        job:jobTitle::STRING AS title,
        job:companyName::STRING AS company_name,
        job:companyLogo::STRING AS company_logo_url,
        job:pubDate::TIMESTAMP AS published_at,
        job:jobLevel::STRING AS level_raw,
        job:jobGeo::STRING AS geo_raw,
        cast(job:jobIndustry AS ARRAY<STRING>) AS industries,
        cast(job:jobType AS ARRAY<STRING>) AS job_types,
        job:jobExcerpt::STRING AS excerpt,
        job:jobDescription::STRING AS description_html,
        job:salaryMin::DOUBLE AS salary_min,
        job:salaryMax::DOUBLE AS salary_max,
        job:salaryCurrency::STRING AS salary_currency,
        job:salaryPeriod::STRING AS salary_period
    FROM jobicy_job_variants
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. History

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW job_history AS
    WITH source_latest_run AS (
        SELECT source, MAX_BY(run_id, landed_at) AS latest_run_id
        FROM observations
        GROUP BY source
    )
    SELECT
        o.source,
        o.source_job_id,
        MIN(o.landed_at) AS first_seen_at,
        MAX(o.landed_at) AS last_seen_at,
        COUNT(DISTINCT o.run_id) AS times_seen,
        BOOL_OR(o.run_id = slr.latest_run_id) AS is_listed_now
    FROM observations AS o
    JOIN source_latest_run AS slr ON o.source = slr.source
    GROUP BY o.source, o.source_job_id
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `silver.jobs`

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW latest_observations AS
    SELECT *
    FROM observations
    QUALIFY ROW_NUMBER() OVER (PARTITION BY source, source_job_id ORDER BY landed_at DESC, run_id DESC) = 1
""")

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.jobs AS
    WITH clean AS (
        SELECT lo.*, clean_html(description_html) AS description_text,
            derive_seniority(title, level_raw) AS s,
            date(published_at) AS published_date,
            CASE lower(coalesce(salary_period, 'yearly'))
                WHEN 'yearly' THEN 1
                WHEN 'monthly' THEN 12
                WHEN 'weekly' THEN 52
                WHEN 'daily' THEN 260
                WHEN 'hourly' THEN 2080
                ELSE NULL
            END AS yearly_factor
        FROM latest_observations AS lo
    ),
    as_of_usd AS (
        SELECT c.*, fx.usd_per_unit, fx.rate_date AS fx_rate_date
        FROM clean AS c
        LEFT JOIN {catalog}.silver.fx_rates AS fx
            ON fx.currency = upper(c.salary_currency)
            AND fx.rate_date <= c.published_date
        QUALIFY ROW_NUMBER() OVER (PARTITION BY c.source, c.source_job_id ORDER BY fx.rate_date DESC) = 1
    )
    SELECT
        as_of_usd.source, as_of_usd.source_job_id, url, title, company_name, company_logo_url, published_at, published_date,
        s.seniority, s.seniority_source, level_raw as source_level, geo_raw, excerpt, description_text,
        salary_min, salary_max, salary_currency, salary_period,
        salary_min * yearly_factor * usd_per_unit AS salary_min_usd_yearly,
        salary_max * yearly_factor * usd_per_unit AS salary_max_usd_yearly,
        fx_rate_date, h.first_seen_at, h.last_seen_at, h.times_seen, h.is_listed_now,
        current_timestamp() AS built_at
    FROM as_of_usd
    JOIN job_history AS h 
        ON as_of_usd.source = h.source 
        AND as_of_usd.source_job_id = h.source_job_id
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Bridge tables

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_industries AS
    SELECT source, source_job_id, EXPLODE(industries) AS industry
    FROM latest_observations
""")

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_types AS
    SELECT source, source_job_id, EXPLODE(job_types) AS job_type
    FROM latest_observations
""")

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_locations AS
    WITH parts AS (
        SELECT source, source_job_id, explode(split(geo_raw, ',')) AS part
        FROM latest_observations
    ),
    locations AS (
        SELECT source, source_job_id, trim(part) AS location_raw
        FROM parts
    )
    SELECT DISTINCT l.source, l.source_job_id, l.location_raw, COALESCE(ref.location_name, l.location_raw) AS location_name,
        COALESCE(ref.location_type, 'unknown') AS location_type, ref.country_code, ref.region
    FROM locations AS l
    LEFT JOIN {catalog}.silver.ref_locations AS ref
        ON lower(l.location_raw) = lower(ref.raw_value)
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

for table in ["jobs", "job_industries", "job_types", "job_locations"]:
    print(f"{catalog}.silver.{table}: {spark.table(f'{catalog}.silver.{table}').count()} rows")

display(spark.sql(f"""
    SELECT title, company_name, published_date, seniority, seniority_source,
           round(salary_min_usd_yearly) AS salary_min_usd, round(salary_max_usd_yearly) AS salary_max_usd,
           times_seen, is_listed_now
    FROM {catalog}.silver.jobs
    ORDER BY published_at DESC
    LIMIT 10
"""))
