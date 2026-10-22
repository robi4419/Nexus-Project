# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze retention: remove expired Himalayas jobs
# MAGIC
# MAGIC Himalayas' API terms say to remove jobs once they expire (Phase 2b, decisions 18, 20 and 22). Each row of
# MAGIC `<catalog>.bronze.himalayas_raw` is one landed file, and each file holds the jobs that expire on one UTC day
# MAGIC (`…/expires_2026-12-19.json`). This notebook:
# MAGIC 1. **deletes** the rows whose expiry day is tomorrow or earlier, the same rule the Airflow DAG uses for landing
# MAGIC    files, so a job is out of every query before it expires;
# MAGIC 2. **purges** them: `REORG TABLE … APPLY (PURGE)` rewrites data files that still hold deleted rows (a `DELETE`
# MAGIC    only marks rows in a *deletion vector*), and `VACUUM` removes the old files once they're older than the
# MAGIC    table's 1-day retention, so the bytes are gone about 1–2 days after expiry.
# MAGIC
# MAGIC Parameter: `catalog` (e.g. `workspace`).

# COMMAND ----------

from datetime import datetime, timedelta, timezone

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")
table = f"{catalog}.bronze.himalayas_raw"

# Jobs expiring on this UTC day or earlier are removed: tomorrow, as for the landing files.
last_day = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()

# The expiry day from the file path, as 'YYYY-MM-DD' text ('' if the path has none). [0-9] and [.] instead of \d
# and \. keep backslashes out of the SQL string. ISO dates compare correctly as text: '2026-10-23' <= '2026-12-19'.
EXPIRY_DAY = "regexp_extract(file_path, 'expires_([0-9]{4}-[0-9]{2}-[0-9]{2})[.]json$', 1)"

if not spark.catalog.tableExists(table):
    dbutils.notebook.exit(f"{table} doesn't exist yet: nothing to remove")

print(f"Removing the rows of {table} whose jobs expire on {last_day} or earlier")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Delete expired rows

# COMMAND ----------

# 1 day instead of Delta's default 7: VACUUM may remove a file one day after it stopped being used. Time travel on
# this table only reaches back that far too. Setting it every run is harmless and keeps it in place.
spark.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ('delta.deletedFileRetentionDuration' = 'interval 1 days')")

deleted = spark.sql(f"""
    DELETE FROM {table}
    WHERE {EXPIRY_DAY} != '' AND {EXPIRY_DAY} <= '{last_day}'
""").first()["num_affected_rows"]
print(f"Deleted {deleted} row(s)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Purge them from storage

# COMMAND ----------

# Rewrites every data file that still holds deleted rows, also any left over by a run that failed before this step.
display(spark.sql(f"REORG TABLE {table} APPLY (PURGE)"))

# Removes files no longer used by the table for more than the 1-day retention.
display(spark.sql(f"VACUUM {table}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

# COMMAND ----------

display(spark.sql(f"""
    SELECT count(*) AS files,
           sum(array_size(cast(body:jobs AS ARRAY<VARIANT>))) AS jobs,
           min({EXPIRY_DAY}) AS earliest_expiry_day,
           max({EXPIRY_DAY}) AS latest_expiry_day,
           count_if({EXPIRY_DAY} = '') AS files_without_expiry_day
    FROM {table}
"""))
