# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: job skills
# MAGIC
# MAGIC Rebuilds `<catalog>.silver.job_skills` from `<catalog>.silver.jobs`: **one row per job and skill** found in the
# MAGIC job's title or description, matched against `databricks/reference/skills.csv` by `transform/skills.py`. Every
# MAGIC row carries the skill list's `taxonomy_version`, so results from different versions of the list can be told apart.
# MAGIC The table is replaced on every run, but it's built from a **persistent cache**: only jobs whose text is new or
# MAGIC changed, or all jobs after a change to the skill list or the matcher's code, are matched again.
# MAGIC
# MAGIC Parameters: `catalog` (e.g. `workspace`) and `bundle_root` (the bundle's files folder; when empty, the repo root
# MAGIC two folders above this notebook is used).

# COMMAND ----------

import os
import sys
import time

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bundle_root", "")

catalog = dbutils.widgets.get("catalog")
bundle_root = dbutils.widgets.get("bundle_root") or os.path.abspath("../..")

# The bundle uploads the repo's transform/ package next to databricks/; make it importable.
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

cache_table = f"{catalog}.silver.cache_job_skills"
print(f"Building {catalog}.silver.job_skills, using transform/ from {bundle_root}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Skill matcher as a SQL function
# MAGIC
# MAGIC `match_skills(title, text, company)` returns an **array of structs**, one per skill found, with the fields `skill`,
# MAGIC `category`, `mentions` and `in_title`. A skill that is part of the employer's own name (Grafana at Grafana Labs)
# MAGIC is skipped. The Python variables hold two fingerprints: `taxonomy_version` (the skill list) and `matcher_version`
# MAGIC (the list and the matcher's code, which versions the cache).

# COMMAND ----------

from pyspark import cloudpickle
from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

import transform
from transform.skills import SkillMatcher

# Same reason as in 04_silver_jobs.py: send transform/'s code to the workers instead of importing it there.
cloudpickle.register_pickle_by_value(transform)

matcher = SkillMatcher.from_csv(f"{bundle_root}/databricks/reference/skills.csv")
taxonomy_version = matcher.taxonomy_version
matcher_version = matcher.matcher_version
print(f"Skill list version {taxonomy_version}, matcher version {matcher_version}")

SKILLS_TYPE = ArrayType(
    StructType(
        [
            StructField("skill", StringType()),
            StructField("category", StringType()),
            StructField("mentions", IntegerType()),
            StructField("in_title", BooleanType()),
        ]
    )
)

spark.udf.register("match_skills", matcher.match, SKILLS_TYPE)

# A quick self-test on the workers: expect Python (2 mentions, in_title), SQL and Kubernetes (2); no Go.
# The second column expects only Python: Grafana is the employer there.
display(spark.sql("""
    SELECT
        match_skills('Senior Python Engineer', 'Python and SQL. Own the Go-to-market plan. Kubernetes (k8s).', 'Acme')
            AS skills,
        match_skills('Data Engineer', 'Grafana Labs builds Grafana. You know Python.', 'Grafana Labs') AS employer_skipped
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Skill cache
# MAGIC
# MAGIC `silver.cache_job_skills` keeps one row per **job text** (`cache_key`, a hash of title, description and company)
# MAGIC and `matcher_version`, with the matched skills. Unlike the other silver tables it is **not** rebuilt: it persists
# MAGIC between runs. Each run:
# MAGIC 1. hashes every current job's text,
# MAGIC 2. matches only the texts that have no cache row for the current `matcher_version` and adds them,
# MAGIC 3. builds `job_skills` by joining jobs to the cache,
# MAGIC 4. deletes cache rows of other versions and of texts no current job has.

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {cache_table} (
        cache_key STRING NOT NULL COMMENT 'sha2 of the job title, description text and company name',
        matcher_version STRING NOT NULL COMMENT 'SkillMatcher.matcher_version: skills.csv rows and skills.py code',
        skills ARRAY<STRUCT<skill: STRING, category: STRING, mentions: INT, in_title: BOOLEAN>>,
        cached_at TIMESTAMP
    )
    COMMENT 'Skill matches by job text and matcher version; kept between runs, unlike the other silver tables'
""")

# Every current job with the hash of exactly what match_skills reads. to_json names each field, so a NULL title can't
# be confused with a NULL description.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW job_keys AS
    SELECT
        source, source_job_id, title, description_text, company_name,
        sha2(to_json(named_struct('title', title, 'text', description_text, 'company', company_name)), 256) AS cache_key
    FROM {catalog}.silver.jobs
""")

# The job texts the cache doesn't cover for this matcher version. Jobs with identical text share one key.
spark.sql(f"""
    CREATE OR REPLACE TEMP VIEW cache_misses AS
    SELECT
        cache_key,
        any_value(title) AS title,
        any_value(description_text) AS description_text,
        any_value(company_name) AS company_name
    FROM job_keys
    LEFT ANTI JOIN (SELECT cache_key FROM {cache_table} WHERE matcher_version = '{matcher_version}') AS cached
        USING (cache_key)
    GROUP BY cache_key
""")

# COMMAND ----------

misses = spark.table("cache_misses").count()
start = time.perf_counter()
# A plain INSERT is enough: a cache row never changes (same text and version, same result), so there is nothing to
# update, and the anti-join above already excludes everything cached. Jobs without skills are cached too (empty array).
spark.sql(f"""
    INSERT INTO {cache_table}
    SELECT cache_key, '{matcher_version}', match_skills(title, description_text, company_name), current_timestamp()
    FROM cache_misses
""")
print(f"Matched {misses} new or changed job texts in {time.perf_counter() - start:.1f} s")

# Safety net: job_skills is built with an inner join, so a job without a cache row would silently lose its skills.
uncached = spark.sql(f"""
    SELECT count(*) FROM job_keys
    LEFT ANTI JOIN (SELECT cache_key FROM {cache_table} WHERE matcher_version = '{matcher_version}') AS cached
        USING (cache_key)
""").first()[0]
if uncached:
    raise Exception(f"{uncached} jobs have no cached skill match for matcher version {matcher_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## `silver.job_skills`
# MAGIC
# MAGIC Columns: `source`, `source_job_id`, `skill`, `category`, `mentions`, `in_title`, `taxonomy_version`.

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_skills AS
    WITH job_skills_cte AS (
        SELECT k.source, k.source_job_id, EXPLODE(c.skills) AS m
        FROM job_keys AS k
        JOIN {cache_table} AS c ON c.cache_key = k.cache_key AND c.matcher_version = '{matcher_version}'
    )
    SELECT source, source_job_id,
        m.skill, m.category, m.mentions, m.in_title, '{taxonomy_version}' AS taxonomy_version
    FROM job_skills_cte
""")

# Keep the cache to what the current jobs need: rows of an older matcher version, or of texts no job has any more
# (e.g. an edited description), are removed.
deleted = spark.sql(f"""
    DELETE FROM {cache_table}
    WHERE matcher_version <> '{matcher_version}' OR cache_key NOT IN (SELECT cache_key FROM job_keys)
""").first()[0]
print(f"Removed {deleted} cache rows no longer needed; cache size {spark.table(cache_table).count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

display(spark.sql(f"""
    SELECT count(*) AS rows,
       count(DISTINCT source, source_job_id) AS jobs_with_skills,
       (SELECT count(*) FROM {catalog}.silver.jobs) AS all_jobs,
       (SELECT count(DISTINCT taxonomy_version) FROM {catalog}.silver.job_skills) AS versions,
       (SELECT first(taxonomy_version) FROM {catalog}.silver.ref_skills) = (SELECT first(taxonomy_version) FROM {catalog}.silver.job_skills) AS same_version
    FROM {catalog}.silver.job_skills
"""))

display(spark.sql(f"""
    SELECT skill, category, count(*) AS jobs_with_skill
    FROM {catalog}.silver.job_skills
    GROUP BY skill, category
    ORDER BY jobs_with_skill DESC
    LIMIT 20
"""))
