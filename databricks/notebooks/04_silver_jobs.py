# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: jobs
# MAGIC
# MAGIC Rebuilds the job tables in `<catalog>.silver` from every landed file in the bronze job tables of Jobicy, Arbeitnow
# MAGIC and Himalayas. All tables are replaced on every run.
# MAGIC
# MAGIC 1. **Observations:** one row per job per landed file. Each source has its own conform `SELECT` that renames its
# MAGIC    fields to one shared set of columns; `UNION ALL` stacks them.
# MAGIC 2. **History:** when each job was first and last seen, in how many runs, and whether it's still listed.
# MAGIC 3. **`silver.jobs`:** the latest version of each job, with plain-text description, seniority, `is_remote`,
# MAGIC    `expires_at` and salary in yearly USD (as-of join to `silver.fx_rates`). Expired Himalayas jobs are left out.
# MAGIC 4. **Bridge tables:** `silver.job_industries`, `silver.job_types` and `silver.job_locations`. Each source's values
# MAGIC    are mapped to ours through the `silver.ref_*` tables; locations are found by `transform/locations.py`.
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
# MAGIC `clean_html(html)`, `derive_seniority(title, fallback_level)` and `title_tech_category(title)` wrap the tested
# MAGIC functions in `transform/`, so the SQL below can call them like built-in functions. `fallback_level` is the highest
# MAGIC of the source's own levels, mapped to ours through `silver.ref_levels`. `derive_seniority` returns a struct: read
# MAGIC its fields with `.seniority` and `.seniority_source`. `title_tech_category` returns the Himalayas Tech category a
# MAGIC title clearly belongs to, or NULL: the same rules that keep a job without a parent category at landing.

# COMMAND ----------

from pyspark import cloudpickle
from pyspark.sql.types import StringType, StructField, StructType

import transform
from transform.seniority import LEVELS, seniority
from transform.tech_titles import tech_category
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


def derive_seniority(title, fallback_level):
    level, source = seniority(title, fallback_level)
    return {"seniority": level, "seniority_source": source}


spark.udf.register("clean_html", html_to_text, StringType())
spark.udf.register("derive_seniority", derive_seniority, SENIORITY_TYPE)
spark.udf.register("title_tech_category", tech_category, StringType())

# Our levels lowest to highest, as a SQL array: array_position() gives each level's rank, so SQL can pick the highest.
LEVELS_SQL = "array(" + ", ".join(f"'{level}'" for level in LEVELS) + ")"
# An empty list of strings, for sources that may leave a list out.
NO_STRINGS = "cast(array() AS ARRAY<STRING>)"

# A quick self-test that runs both functions on the workers, not only here on the driver.
display(spark.sql("""
    SELECT clean_html('<p>Python &amp; SQL</p><ul><li>dbt</li></ul>') AS cleaned,
           clean_html('&lt;p&gt;Escaped once more&lt;/p&gt;<p>Find jobs on Arbeitnow</p>') AS cleaned_escaped,
           derive_seniority('Sr. Data Engineer', NULL) AS from_title,
           derive_seniority('Data Analyst', 'Mid') AS from_source_level,
           title_tech_category('SAP FICO Consultant') AS tech_category
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Observations
# MAGIC
# MAGIC Temp view `observations`: one row per job per landed file, with the same columns from every source.
# MAGIC
# MAGIC | Column | Jobicy | Arbeitnow | Himalayas |
# MAGIC |---|---|---|---|
# MAGIC | `source_job_id` | `id` | `slug` | `guid` |
# MAGIC | `url` | `url` | `url` | `applicationLink` (API terms) |
# MAGIC | `published_at` | `pubDate` | `created_at` | `pubDate` (last updated) |
# MAGIC | `expires_at` | | | `expiryDate` |
# MAGIC | `is_remote` | true | `remote` | true |
# MAGIC | `levels_raw` | `[jobLevel]` | `job_types` + `tags` | `seniority` |
# MAGIC | `locations_raw` | `jobGeo` split at `,` | `location` split at `;` | `locationRestrictions`, empty = `['Worldwide']` |
# MAGIC | `industries_raw` | `jobIndustry` | `tags` | `parentCategories`; without any, the title's Tech category |
# MAGIC | `job_types_raw` | `jobType` | `job_types` | `[employmentType]` |
# MAGIC
# MAGIC Plus `run_id`, `landed_at`, `title`, `company_name`, `company_logo_url`, `excerpt`, `description_html` and the
# MAGIC salary fields (Arbeitnow has none).

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW observations AS
    WITH jobicy AS (
        SELECT run_id, landed_at, explode(cast(body:jobs AS ARRAY<VARIANT>)) AS job
        FROM {catalog}.bronze.jobicy_raw
    ),
    arbeitnow AS (
        SELECT run_id, landed_at, job,
            coalesce(cast(job:job_types AS ARRAY<STRING>), {NO_STRINGS}) AS job_types,
            coalesce(cast(job:tags AS ARRAY<STRING>), {NO_STRINGS}) AS tags
        FROM (
            SELECT run_id, landed_at, explode(cast(body:data AS ARRAY<VARIANT>)) AS job
            FROM {catalog}.bronze.arbeitnow_raw
        )
    ),
    himalayas AS (
        SELECT run_id, landed_at, job, cast(job:locationRestrictions AS ARRAY<STRING>) AS countries,
            coalesce(cast(job:parentCategories AS ARRAY<STRING>), {NO_STRINGS}) AS parents
        FROM (
            SELECT run_id, landed_at, explode(cast(body:jobs AS ARRAY<VARIANT>)) AS job
            FROM {catalog}.bronze.himalayas_raw
        )
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
        CAST(NULL AS TIMESTAMP) AS expires_at,
        true AS is_remote,  -- a remote-jobs feed
        filter(array(job:jobLevel::STRING), level -> level IS NOT NULL) AS levels_raw,
        transform(split(job:jobGeo::STRING, ','), place -> trim(place)) AS locations_raw,  -- "USA, Canada"
        cast(job:jobIndustry AS ARRAY<STRING>) AS industries_raw,
        cast(job:jobType AS ARRAY<STRING>) AS job_types_raw,
        job:jobExcerpt::STRING AS excerpt,
        job:jobDescription::STRING AS description_html,
        job:salaryMin::DOUBLE AS salary_min,
        job:salaryMax::DOUBLE AS salary_max,
        job:salaryCurrency::STRING AS salary_currency,
        job:salaryPeriod::STRING AS salary_period
    FROM jobicy

    UNION ALL

    SELECT
        'arbeitnow' AS source,
        job:slug::STRING AS source_job_id,
        run_id, landed_at,
        job:url::STRING AS url,
        job:title::STRING AS title,
        job:company_name::STRING AS company_name,
        CAST(NULL AS STRING) AS company_logo_url,
        timestamp_seconds(job:created_at::BIGINT) AS published_at,
        CAST(NULL AS TIMESTAMP) AS expires_at,
        job:remote::BOOLEAN AS is_remote,
        -- levels hide among the job types and tags ("berufserfahren", "Team Leader"); levels.csv says which they are
        concat(job_types, tags) AS levels_raw,
        -- one place, sometimes several: "Bristol; Cambridge". An empty location stays one (unknown) entry.
        transform(split(coalesce(job:location::STRING, ''), ';'), place -> trim(place)) AS locations_raw,
        tags AS industries_raw,
        job_types AS job_types_raw,
        CAST(NULL AS STRING) AS excerpt,
        job:description::STRING AS description_html,
        CAST(NULL AS DOUBLE) AS salary_min,
        CAST(NULL AS DOUBLE) AS salary_max,
        CAST(NULL AS STRING) AS salary_currency,
        CAST(NULL AS STRING) AS salary_period
    FROM arbeitnow

    UNION ALL

    SELECT
        'himalayas' AS source,
        job:guid::STRING AS source_job_id,
        run_id, landed_at,
        job:applicationLink::STRING AS url,  -- API terms: every Apply uses applicationLink
        job:title::STRING AS title,
        job:companyName::STRING AS company_name,
        job:companyLogo::STRING AS company_logo_url,
        timestamp_seconds(job:pubDate::BIGINT) AS published_at,
        timestamp_seconds(job:expiryDate::BIGINT) AS expires_at,
        true AS is_remote,  -- a remote-jobs feed
        coalesce(cast(job:seniority AS ARRAY<STRING>), {NO_STRINGS}) AS levels_raw,
        -- country names; no restriction means the job can be done from anywhere
        CASE WHEN array_size(countries) > 0 THEN countries ELSE array('Worldwide') END AS locations_raw,
        -- a job landed for its title alone has no parent category: the same title rules give it one (Phase 4, decision 8)
        CASE WHEN array_size(parents) > 0 THEN parents
            ELSE array_compact(array(title_tech_category(job:title::STRING)))
        END AS industries_raw,
        array(job:employmentType::STRING) AS job_types_raw,
        job:excerpt::STRING AS excerpt,
        job:description::STRING AS description_html,
        job:minSalary::DOUBLE AS salary_min,
        job:maxSalary::DOUBLE AS salary_max,
        job:currency::STRING AS salary_currency,
        job:salaryPeriod::STRING AS salary_period
    FROM himalayas
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. History
# MAGIC
# MAGIC `in_latest_runs`: the job is in its source's latest run, or for Arbeitnow in either of its last two runs, because
# MAGIC one Arbeitnow download misses about 1% of the feed at random (Phase 2b, decision 17). Himalayas is fetched
# MAGIC incrementally, so there `is_listed_now` comes from `expires_at` instead (section 3).

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW job_history AS
    WITH runs AS (
        -- each source's runs, newest first: run_rank 1 is its latest run
        SELECT source, run_id, dense_rank() OVER (PARTITION BY source ORDER BY max(landed_at) DESC) AS run_rank
        FROM observations
        GROUP BY source, run_id
    )
    SELECT
        o.source,
        o.source_job_id,
        min(o.landed_at) AS first_seen_at,
        max(o.landed_at) AS last_seen_at,
        count(DISTINCT o.run_id) AS times_seen,
        bool_or(r.run_rank <= CASE o.source WHEN 'arbeitnow' THEN 2 ELSE 1 END) AS in_latest_runs
    FROM observations AS o
    JOIN runs AS r ON o.source = r.source AND o.run_id = r.run_id
    GROUP BY o.source, o.source_job_id
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. `silver.jobs`

# COMMAND ----------

# The latest version of each job. The expiry filter comes after picking the latest version, so an older copy can't
# stand in for a job whose latest copy has expired.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW latest_observations AS
    SELECT *
    FROM (
        SELECT *
        FROM observations
        QUALIFY ROW_NUMBER() OVER (PARTITION BY source, source_job_id ORDER BY landed_at DESC, run_id DESC) = 1
    )
    -- API terms: expired Himalayas jobs are left out (bronze retention normally removed them already)
    WHERE expires_at IS NULL OR expires_at > current_timestamp()
""")

# Each job's own level values that levels.csv lists, and the highest of them mapped to ours: the seniority fallback
# when the title has no level. Values reviewed as unreliable (Jobicy's "Director", "Any") map to NULL and aren't used.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW job_levels AS
    WITH raw AS (
        SELECT source, source_job_id, explode(levels_raw) AS raw_level
        FROM latest_observations
    )
    SELECT
        r.source,
        r.source_job_id,
        array_sort(collect_set(r.raw_level)) AS source_levels,
        max_by(lvl.seniority, array_position({LEVELS_SQL}, lvl.seniority))
            FILTER (WHERE lvl.seniority IS NOT NULL) AS fallback_level
    FROM raw AS r
    JOIN {catalog}.silver.ref_levels AS lvl
        ON lvl.source = r.source AND lower(lvl.raw_value) = lower(r.raw_level)
    GROUP BY r.source, r.source_job_id
""")

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.jobs AS
    WITH clean AS (
        SELECT lo.*, clean_html(lo.description_html) AS description_text,
            derive_seniority(lo.title, lv.fallback_level) AS s,
            coalesce(lv.source_levels, {NO_STRINGS}) AS source_levels,
            date(lo.published_at) AS published_date,
            CASE lower(coalesce(lo.salary_period, 'yearly'))
                WHEN 'yearly' THEN 1
                WHEN 'annual' THEN 1
                WHEN 'monthly' THEN 12
                WHEN 'fortnightly' THEN 26
                WHEN 'weekly' THEN 52
                WHEN 'daily' THEN 260
                WHEN 'hourly' THEN 2080
                ELSE NULL
            END AS yearly_factor
        FROM latest_observations AS lo
        LEFT JOIN job_levels AS lv ON lv.source = lo.source AND lv.source_job_id = lo.source_job_id
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
        as_of_usd.source, as_of_usd.source_job_id, url, title, company_name, company_logo_url,
        published_at, published_date, expires_at, is_remote,
        s.seniority, s.seniority_source, source_levels, locations_raw, excerpt, description_text,
        salary_min, salary_max, salary_currency, salary_period,
        salary_min * yearly_factor * usd_per_unit AS salary_min_usd_yearly,
        salary_max * yearly_factor * usd_per_unit AS salary_max_usd_yearly,
        fx_rate_date, h.first_seen_at, h.last_seen_at, h.times_seen,
        CASE
            WHEN as_of_usd.source = 'himalayas' THEN expires_at > current_timestamp()
            ELSE h.in_latest_runs
        END AS is_listed_now,
        current_timestamp() AS built_at
    FROM as_of_usd
    JOIN job_history AS h
        ON as_of_usd.source = h.source
        AND as_of_usd.source_job_id = h.source_job_id
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Bridge tables
# MAGIC
# MAGIC Industries and job types map each source's values to ours through `silver.ref_industries` and
# MAGIC `silver.ref_job_types`; values reviewed and deliberately not mapped (an empty target in the CSV) give no row.

# COMMAND ----------

for table, raw_column, mapping, target in [
    ("job_industries", "industries_raw", "ref_industries", "industry"),
    ("job_types", "job_types_raw", "ref_job_types", "job_type"),
]:
    spark.sql(f"""
        CREATE OR REPLACE TABLE {catalog}.silver.{table} AS
        WITH raw AS (
            SELECT source, source_job_id, explode({raw_column}) AS raw_value
            FROM latest_observations
        )
        SELECT DISTINCT r.source, r.source_job_id, m.{target}
        FROM raw AS r
        JOIN {catalog}.silver.{mapping} AS m
            ON m.source = r.source AND lower(m.raw_value) = lower(r.raw_value)
        WHERE m.{target} IS NOT NULL
    """)

# COMMAND ----------

# MAGIC %md
# MAGIC Locations: each **distinct** raw value (a few hundred) is located once by `transform/locations.Locator` here on the
# MAGIC driver, which reads `locations.csv`, `countries.csv` and `cities.csv`. The results become the temp view `located`,
# MAGIC joined back to every job. An unknown place keeps its cleaned text as `location_name`; an empty one has none.

# COMMAND ----------

from transform.locations import Locator

locator = Locator.from_csv(f"{bundle_root}/databricks/reference")

raw_values = [
    row["location_raw"]
    for row in spark.sql("""
        SELECT DISTINCT location_raw
        FROM (SELECT explode(locations_raw) AS location_raw FROM latest_observations)
    """).collect()
]
LOCATED_COLUMNS = ["location_raw", "location_name", "location_type", "country_code", "region"]
LOCATED_TYPE = StructType([StructField(name, StringType()) for name in LOCATED_COLUMNS])
spark.createDataFrame(
    [(raw, *locator.locate(raw)) for raw in raw_values], LOCATED_TYPE
).createOrReplaceTempView("located")
print(f"Located {len(raw_values)} distinct raw location values")

# COMMAND ----------

# <=> is "equal, counting two NULLs as equal", so a missing value still finds its (unknown) row.
spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_locations AS
    WITH raw AS (
        SELECT source, source_job_id, explode(locations_raw) AS location_raw
        FROM latest_observations
    )
    SELECT DISTINCT r.source, r.source_job_id, r.location_raw,
        l.location_name, l.location_type, l.country_code, l.region
    FROM raw AS r
    JOIN located AS l ON r.location_raw <=> l.location_raw
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

for table in ["jobs", "job_industries", "job_types", "job_locations"]:
    print(f"{catalog}.silver.{table}: {spark.table(f'{catalog}.silver.{table}').count()} rows")

display(spark.sql(f"""
    SELECT source,
        count(*) AS jobs,
        count_if(is_listed_now) AS listed_now,
        count_if(is_remote) AS remote,
        count_if(seniority = 'Unspecified') AS seniority_unspecified,
        count_if(salary_min_usd_yearly IS NOT NULL OR salary_max_usd_yearly IS NOT NULL) AS with_usd_salary,
        min(published_date) AS oldest,
        max(published_date) AS newest
    FROM {catalog}.silver.jobs
    GROUP BY source
    ORDER BY source
"""))

display(spark.sql(f"""
    SELECT source, location_type, count(*) AS rows
    FROM {catalog}.silver.job_locations
    GROUP BY source, location_type
    ORDER BY source, rows DESC
"""))
