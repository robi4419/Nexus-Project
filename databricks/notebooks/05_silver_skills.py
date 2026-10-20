# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: job skills
# MAGIC
# MAGIC Rebuilds `<catalog>.silver.job_skills` from `<catalog>.silver.jobs`: **one row per job and skill** found in the
# MAGIC job's title or description, matched against `databricks/reference/skills.csv` by `transform/skills.py`. Every
# MAGIC row carries the skill list's `taxonomy_version`, so results from different versions of the list can be told apart.
# MAGIC The table is replaced on every run.
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

print(f"Building {catalog}.silver.job_skills, using transform/ from {bundle_root}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Skill matcher as a SQL function
# MAGIC
# MAGIC `match_skills(title, text, company)` returns an **array of structs**, one per skill found, with the fields `skill`,
# MAGIC `category`, `mentions` and `in_title`. A skill that is part of the employer's own name (Grafana at Grafana Labs)
# MAGIC is skipped. The Python variable `taxonomy_version` holds the skill list's fingerprint.

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
print(f"Skill list version {taxonomy_version}")

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
# MAGIC ## `silver.job_skills`
# MAGIC
# MAGIC Columns: `source`, `source_job_id`, `skill`, `category`, `mentions`, `in_title`, `taxonomy_version`.

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {catalog}.silver.job_skills AS
    WITH job_skills_cte AS (
        SELECT source, source_job_id,
            EXPLODE(match_skills(title, description_text, company_name)) AS m
        FROM {catalog}.silver.jobs
    )
    SELECT source, source_job_id,
        m.skill, m.category, m.mentions, m.in_title, '{taxonomy_version}' AS taxonomy_version
    FROM job_skills_cte
""")

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
