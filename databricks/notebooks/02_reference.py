# Databricks notebook source
# MAGIC %md
# MAGIC # Reference data
# MAGIC
# MAGIC Loads the version-controlled lookup files `databricks/reference/*.csv` (uploaded by the bundle) into
# MAGIC `<catalog>.silver.ref_locations` and `<catalog>.silver.ref_skills`. Both tables are replaced on every run,
# MAGIC so changing a mapping only takes editing the CSV and running `databricks bundle deploy`.
# MAGIC
# MAGIC `ref_skills` also gets the skill list's `taxonomy_version` (see `transform/skills.py`).
# MAGIC
# MAGIC Parameters: `catalog` and `bundle_root` (the bundle's files folder; when empty, the repo root two folders above
# MAGIC this notebook is used).

# COMMAND ----------

import os
import sys

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bundle_root", "")

catalog = dbutils.widgets.get("catalog")
bundle_root = dbutils.widgets.get("bundle_root") or os.path.abspath("../..")

reference_dir = f"{bundle_root}/databricks/reference"
print(f"Reading reference CSVs from {reference_dir}")

# The bundle uploads the repo's transform/ package next to databricks/; make it importable.
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

# COMMAND ----------

spark.sql(
    f"CREATE SCHEMA IF NOT EXISTS {catalog}.silver "
    "COMMENT 'Cleaned, deduplicated and normalised data built from bronze'"
)

# COMMAND ----------

import pandas as pd


def read_reference_csv(name: str) -> pd.DataFrame:
    # dtype=str and keep_default_na=False: read every value as text, exactly as written
    # (otherwise pandas would turn e.g. "NA" (Namibia) or an empty cell into a missing number).
    return pd.read_csv(f"{reference_dir}/{name}", dtype=str, keep_default_na=False, encoding="utf-8")


def replace_table(frame: pd.DataFrame, table: str) -> None:
    full_name = f"{catalog}.silver.{table}"
    (
        spark.createDataFrame(frame)
        .write.mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable(full_name)
    )
    print(f"{full_name}: {len(frame)} rows")


# COMMAND ----------

locations = read_reference_csv("locations.csv")
locations["country_code"] = [code or None for code in locations["country_code"]]  # regions: "" -> NULL
replace_table(locations, "ref_locations")

from transform.skills import SkillMatcher

skills = read_reference_csv("skills.csv")
skills["case_sensitive"] = skills["case_sensitive"] == "true"
# The same fingerprint silver_skills stores in job_skills, so a check can prove both came from the same list.
skills["taxonomy_version"] = SkillMatcher.from_csv(f"{reference_dir}/skills.csv").taxonomy_version
replace_table(skills, "ref_skills")

# COMMAND ----------

display(
    spark.sql(f"""
        SELECT category, count(*) AS skills
        FROM {catalog}.silver.ref_skills
        GROUP BY category
        ORDER BY skills DESC
    """)
)
