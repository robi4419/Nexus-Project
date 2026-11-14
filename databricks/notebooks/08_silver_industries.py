# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: job industries
# MAGIC
# MAGIC Rebuilds `<catalog>.silver.job_industry_predictions`: **one row per job posting** with the industry model's
# MAGIC answer (Phase 5, decision 15). The model reads the posting's title and its skills from `silver.job_skills`.
# MAGIC
# MAGIC - The model is **not trained here.** `train_industry_model.py` trains and saves it by hand; this task loads the
# MAGIC   newest version listed in `silver.industry_models`.
# MAGIC - **No threshold here.** Every posting gets the most likely industry and group with their probabilities; dbt
# MAGIC   decides from which probability a job shows them (`int_job_industries`).
# MAGIC - A group's probability is the sum over its industries, so the model can be sure of "Software" while unsure
# MAGIC   between Backend and Full-stack.
# MAGIC
# MAGIC Columns: `source`, `source_job_id`, `industry`, `industry_probability`, `industry_group`, `group_probability`,
# MAGIC `model_version`.
# MAGIC
# MAGIC Parameters: `catalog` (e.g. `workspace`) and `bundle_root` (the bundle's files folder; when empty, the repo root
# MAGIC two folders above this notebook is used).

# COMMAND ----------

# MAGIC %pip install scikit-learn==1.9.1 joblib==1.6.0

# COMMAND ----------

# The saved model only loads with the scikit-learn version it was saved with, hence the install above. It only
# reaches Python after a restart; everything below runs in the restarted Python.
dbutils.library.restartPython()

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

silver = f"{catalog}.silver"
print(f"Building {silver}.job_industry_predictions, using transform/ from {bundle_root}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## The newest model

# COMMAND ----------

# Until gold reads the predictions (Phase 5, task 5.12, step 5), a missing model only skips this task, so deploying
# the bundle before the first training can't break the nightly run. From step 5 on it must fail instead.
newest = None
if spark.catalog.tableExists(f"{silver}.industry_models"):
    newest = spark.sql(f"""
        SELECT model_version, model_path
        FROM {silver}.industry_models
        ORDER BY trained_at DESC
        LIMIT 1
    """).first()
if newest is None:
    dbutils.notebook.exit(f"No model in {silver}.industry_models yet: nothing predicted")

from transform.industry_model import IndustryModel

model_version, model_path = newest["model_version"], newest["model_path"]
model = IndustryModel.load(model_path)
print(f"Model {model_version} from {model_path}: {len(model.classes)} industries in {len(model.groups)} groups")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Predict every posting
# MAGIC
# MAGIC The titles and skills of all postings are read to the driver and predicted there: tens of thousands of short
# MAGIC texts take seconds, and the fitted model doesn't have to be sent to the workers.

# COMMAND ----------

postings = spark.sql(f"""
    WITH skills AS (
        SELECT source, source_job_id, sort_array(collect_set(skill)) AS skills
        FROM {silver}.job_skills
        GROUP BY source, source_job_id
    )
    SELECT j.source, j.source_job_id, j.title, coalesce(s.skills, array()) AS skills
    FROM {silver}.jobs AS j
    LEFT JOIN skills AS s ON s.source = j.source AND s.source_job_id = j.source_job_id
""").collect()

start = time.perf_counter()
answers = model.predict([{"title": row["title"], "skills": list(row["skills"])} for row in postings])
print(f"Predicted {len(postings)} postings in {time.perf_counter() - start:.1f} s")

(
    spark.createDataFrame(
        [
            (row["source"], row["source_job_id"], industry, probability, group, group_probability, model_version)
            for row, (industry, probability, group, group_probability) in zip(postings, answers)
        ],
        "source STRING, source_job_id STRING, industry STRING, industry_probability DOUBLE, "
        "industry_group STRING, group_probability DOUBLE, model_version STRING",
    )
    .write.mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{silver}.job_industry_predictions")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC `sure` and `group_sure` count the postings at 50% or more, the threshold dbt uses (`industry_sure`).

# COMMAND ----------

display(spark.sql(f"""
    SELECT source,
        count(*) AS postings,
        round(100 * avg(CAST(industry_probability >= 0.5 AS INT)), 1) AS sure_pct,
        round(100 * avg(CAST(group_probability >= 0.5 AS INT)), 1) AS group_sure_pct
    FROM {silver}.job_industry_predictions
    GROUP BY source
    ORDER BY source
"""))

display(spark.sql(f"""
    SELECT industry_group, industry, count(*) AS postings, count_if(industry_probability >= 0.5) AS sure
    FROM {silver}.job_industry_predictions
    GROUP BY industry_group, industry
    ORDER BY postings DESC
"""))
