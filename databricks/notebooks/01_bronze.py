# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze: load newly landed files
# MAGIC
# MAGIC Loads every **new** JSON file from `/Volumes/<catalog>/bronze/landing/<source>/` into the Delta table
# MAGIC `<catalog>.bronze.<source>_raw`: **one row per file**, with the whole document kept untouched in the VARIANT
# MAGIC column `body`. Auto Loader remembers which files it has already loaded (in a checkpoint), so each file is
# MAGIC loaded exactly once; a file re-written by an Airflow retry is loaded again as a new row.
# MAGIC
# MAGIC Parameters: `catalog` (e.g. `workspace`) and `source` (`jobicy` or `frankfurter`).

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("source", "jobicy")

catalog = dbutils.widgets.get("catalog")
source = dbutils.widgets.get("source")

landing_path = f"/Volumes/{catalog}/bronze/landing/{source}/"
checkpoint_path = f"/Volumes/{catalog}/bronze/checkpoints/{source}_raw"
table = f"{catalog}.bronze.{source}_raw"

print(f"Loading new files from {landing_path} into {table}")

# COMMAND ----------

spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze.checkpoints "
    "COMMENT 'Auto Loader checkpoints: which landed files each bronze table has already loaded'"
)
rows_before = spark.table(table).count() if spark.catalog.tableExists(table) else 0

# COMMAND ----------

from pyspark.sql import functions as F

file_path = F.col("_metadata.file_path")

new_files = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "json")
    .option("multiLine", "true")
    .option("singleVariantColumn", "body")
    .option("cloudFiles.allowOverwrites", "true")
    .load(landing_path)
    .select(
        F.lit(source).alias("source"),
        file_path.alias("file_path"),
        F.to_date(F.regexp_extract(file_path, r"ingest_date=(\d{4}-\d{2}-\d{2})", 1)).alias("ingest_date"),
        F.regexp_extract(file_path, r"run=([^/]+)", 1).alias("run_id"),
        F.col("_metadata.file_modification_time").alias("landed_at"),
        F.current_timestamp().alias("loaded_at"),
        F.col("body"),
    )
)

# COMMAND ----------

query = (
    new_files.writeStream
    .option("checkpointLocation", checkpoint_path)
    .trigger(availableNow=True)
    .toTable(table)
)
query.awaitTermination()

# COMMAND ----------

rows_after = spark.table(table).count()
print(f"Loaded {rows_after - rows_before} new file(s); {table} now has {rows_after} rows.")

display(
    spark.sql(f"""
        SELECT ingest_date, count(*) AS files, count(DISTINCT run_id) AS runs, max(loaded_at) AS last_loaded_at
        FROM {table}
        GROUP BY ingest_date
        ORDER BY ingest_date
    """)
)
