# Databricks notebook source
# MAGIC %md
# MAGIC # Train the industry model (run by hand)
# MAGIC
# MAGIC Trains the model that gives every job its industry (Phase 5, decision 15), scores it on the test set, saves it
# MAGIC and records it in `<catalog>.silver.industry_models`. **Not part of the nightly Job:** run it after
# MAGIC `scripts/upload_industry_labels.py` changed `silver.industry_labels`. The nightly task `silver_industries` then
# MAGIC uses the newest model.
# MAGIC
# MAGIC 1. **Read** the hand labels with each job's title and skills from gold. A label whose job has left gold can't be
# MAGIC    used: its title is gone.
# MAGIC 2. **Fit** on the `train` labels and **score** on the `test` labels, which are never trained on. The test jobs
# MAGIC    are scored twice: from the job's inputs, and from the inputs of the one posting that speaks for the job, which
# MAGIC    is what the nightly task has.
# MAGIC 3. **Save** the fitted model to `/Volumes/<catalog>/silver/models/industry/<model_version>/model.joblib`.
# MAGIC 4. **Record** the version with its label counts and scores. The scores can't be measured again once the test
# MAGIC    jobs expire, so this row is their record.
# MAGIC
# MAGIC This notebook prints counts and scores only, never a job's title.
# MAGIC
# MAGIC Parameters: `catalog`, `bundle_root` (empty: the repo root two folders above this notebook), `sure` (the
# MAGIC probability from which an answer counts as given, for the scores only) and `model_version` (empty: today's date
# MAGIC and the number of labels trained on, e.g. `2026-11-14-3100`).

# COMMAND ----------

# MAGIC %pip install scikit-learn==1.9.1 joblib==1.6.0

# COMMAND ----------

# The install above only reaches Python after a restart. Everything below runs in the restarted Python.
dbutils.library.restartPython()

# COMMAND ----------

import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("bundle_root", "")
dbutils.widgets.text("sure", "0.5")
dbutils.widgets.text("model_version", "")

catalog = dbutils.widgets.get("catalog")
bundle_root = dbutils.widgets.get("bundle_root") or os.path.abspath("../..")
sure = float(dbutils.widgets.get("sure"))

# The bundle uploads the repo's transform/ package next to databricks/; make it importable.
if bundle_root not in sys.path:
    sys.path.insert(0, bundle_root)

import sklearn

from transform.industry_model import IndustryModel, score

silver, gold, staging = f"{catalog}.silver", f"{catalog}.gold", f"{catalog}.gold_staging"
print(f"scikit-learn {sklearn.__version__}; transform/ from {bundle_root}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Labels with their jobs

# COMMAND ----------

labelled = spark.sql(f"""
    WITH skills AS (
        SELECT job_key, sort_array(collect_set(skill)) AS skills
        FROM {gold}.fct_job_skills
        GROUP BY job_key
    )
    SELECT l.job_key, l.industry, l.also_acceptable, l.split, f.title, coalesce(s.skills, array()) AS skills
    FROM {silver}.industry_labels AS l
    JOIN {gold}.fct_job_postings AS f ON f.job_key = l.job_key
    LEFT JOIN skills AS s ON s.job_key = l.job_key
    ORDER BY l.job_key
""").collect()

in_table = {
    row["split"]: row["labels"]
    for row in spark.sql(f"SELECT split, count(*) AS labels FROM {silver}.industry_labels GROUP BY split").collect()
}


def as_job(row):
    return {"title": row["title"], "skills": list(row["skills"] or [])}


train = [row for row in labelled if row["split"] == "train"]
test = [row for row in labelled if row["split"] == "test"]
print(f"train: {len(train)} usable of {in_table.get('train', 0)} labels; "
      f"test: {len(test)} usable of {in_table.get('test', 0)}")
if not train or not test:
    raise Exception("No usable labels: upload them with scripts/upload_industry_labels.py first")

model_version = dbutils.widgets.get("model_version") or (
    f"{datetime.now(timezone.utc).date().isoformat()}-{len(train)}"
)
print(f"model version {model_version}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Fit and score

# COMMAND ----------

model = IndustryModel().fit([as_job(row) for row in train], [row["industry"] for row in train])

# Per test job: the best industry first, then the others the guide also accepts.
acceptable = [[row["industry"], *(row["also_acceptable"] or [])] for row in test]
job_scores = score(model.predict([as_job(row) for row in test]), acceptable, sure)

# The posting that speaks for each test job (the rule of fct_job_postings), with that posting's own skills.
spark.createDataFrame([(row["job_key"],) for row in test], "job_key STRING").createOrReplaceTempView("test_keys")
postings = {
    row["job_key"]: row
    for row in spark.sql(f"""
        WITH ranked AS (
            SELECT p.job_key, p.source, p.source_job_id, p.title,
                row_number() OVER (
                    PARTITION BY p.job_key ORDER BY p.is_listed_now DESC, p.published_at DESC, p.posting_key
                ) AS listing_rank
            FROM {staging}.int_job_postings AS p
            JOIN test_keys USING (job_key)
        )
        SELECT r.job_key, r.title, sort_array(collect_set(s.skill)) AS skills
        FROM ranked AS r
        LEFT JOIN {silver}.job_skills AS s ON s.source = r.source AND s.source_job_id = r.source_job_id
        WHERE r.listing_rank = 1
        GROUP BY r.job_key, r.title
    """).collect()
}
posting_scores = score(model.predict([as_job(postings[row["job_key"]]) for row in test]), acceptable, sure)

display(spark.createDataFrame(
    [(name, *[round(float(value), 4) for value in scores.values()])
     for name, scores in [("job inputs", job_scores), ("posting inputs", posting_scores)]],
    ["scored from", *job_scores.keys()],
))

# The nightly task predicts postings. If that scored clearly worse than the job inputs the labels were made with,
# stop here: nothing has been saved yet.
if job_scores["industry_right"] - posting_scores["industry_right"] > 0.01:
    raise Exception(
        f"Posting inputs score {posting_scores['industry_right']:.1%} against {job_scores['industry_right']:.1%} "
        "from job inputs: more than a point lower. The model was not saved."
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Save
# MAGIC
# MAGIC The file holds the fitted scikit-learn parts: weights per word, letter group and skill. It holds no job.

# COMMAND ----------

spark.sql(f"""
    CREATE VOLUME IF NOT EXISTS {silver}.models
    COMMENT 'Fitted models the nightly Job applies; written by hand-run training notebooks'
""")
model_dir = f"/Volumes/{catalog}/silver/models/industry/{model_version}"
model_path = f"{model_dir}/model.joblib"
if os.path.exists(model_path):
    raise Exception(f"{model_path} exists already: a saved version is never overwritten. Pass another model_version.")

# Written to local disk first and copied over in one go: a Volume takes whole files best.
with tempfile.TemporaryDirectory() as local_dir:
    local_path = f"{local_dir}/model.joblib"
    model.save(local_path)
    os.makedirs(model_dir, exist_ok=True)
    shutil.copy(local_path, model_path)

# Read it back the way the nightly task will, and compare.
reloaded = IndustryModel.load(model_path)
if reloaded.predict([as_job(row) for row in test]) != model.predict([as_job(row) for row in test]):
    raise Exception(f"The model read back from {model_path} answers differently from the one just trained")
print(f"Saved {model_path} ({os.path.getsize(model_path) / 1e6:.1f} MB), and it reads back with the same answers")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Record

# COMMAND ----------

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {silver}.industry_models (
        model_version STRING NOT NULL COMMENT 'Also the folder under /Volumes/<catalog>/silver/models/industry/',
        trained_at TIMESTAMP NOT NULL,
        model_path STRING NOT NULL,
        sklearn_version STRING NOT NULL COMMENT 'The model file only loads with this scikit-learn version',
        train_labels INT COMMENT 'Training labels in silver.industry_labels when trained',
        train_labels_used INT COMMENT 'Those whose job was still in gold, so its title could be read',
        test_jobs INT COMMENT 'Test-set jobs in silver.industry_labels when trained',
        test_jobs_used INT COMMENT 'Those whose job was still in gold',
        sure DOUBLE COMMENT 'The probability from which an answer counts as given, for the scores below',
        industry_right DOUBLE COMMENT 'Share of test jobs whose industry is one the guide accepts',
        best_right DOUBLE COMMENT 'Share whose industry is the best one',
        answered DOUBLE COMMENT 'Share whose industry has at least `sure` probability',
        right_when_answered DOUBLE COMMENT 'industry_right among the answered',
        group_right DOUBLE,
        group_answered DOUBLE,
        group_right_when_answered DOUBLE
    )
    COMMENT 'One row per trained industry model, with its test scores; kept between runs (Phase 5, decision 15)'
""")

spark.createDataFrame(
    [(
        model_version, datetime.now(timezone.utc), model_path, sklearn.__version__,
        in_table.get("train", 0), len(train), in_table.get("test", 0), len(test), sure,
        *[float(job_scores[name]) for name in (
            "industry_right", "best_right", "answered", "right_when_answered",
            "group_right", "group_answered", "group_right_when_answered",
        )],
    )],
    spark.table(f"{silver}.industry_models").schema,
).write.mode("append").saveAsTable(f"{silver}.industry_models")

display(spark.sql(f"SELECT * FROM {silver}.industry_models ORDER BY trained_at DESC"))
