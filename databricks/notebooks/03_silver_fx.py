# Databricks notebook source
# MAGIC %md
# MAGIC # Silver: exchange rates
# MAGIC
# MAGIC Rebuilds `<catalog>.silver.fx_rates` from `<catalog>.bronze.frankfurter_raw`:
# MAGIC **one row per rate_date and currency**, plus a USD row (= 1.0) for each date. The table is replaced on every run.
# MAGIC
# MAGIC - `rate_date` is the ECB date inside the file (`body:date`), not the folder's `ingest_date`: on an ECB holiday
# MAGIC   the API returns the previous working day's rates, so two files can hold the same date.
# MAGIC - When several files hold the same date (holiday, a file re-landed by an Airflow Clear, a repeated backfill),
# MAGIC   the most recently landed file wins.
# MAGIC - `units_per_usd` is the API's value (1 USD = 0.89 EUR); `usd_per_unit` is its inverse (1 EUR = 1.12 USD).
# MAGIC
# MAGIC Parameters: `catalog` (e.g. `workspace`).

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")

catalog = dbutils.widgets.get("catalog")

frankfurter_raw_table = f"{catalog}.bronze.frankfurter_raw"
silver_fx_table = f"{catalog}.silver.fx_rates"

print(f"Rebuilding {silver_fx_table} from {frankfurter_raw_table}")

# COMMAND ----------

spark.sql(
    f"CREATE SCHEMA IF NOT EXISTS {catalog}.silver "
    "COMMENT 'Cleaned, deduplicated and normalised data built from bronze'"
)

# COMMAND ----------

spark.sql(f"""
    CREATE OR REPLACE TABLE {silver_fx_table} AS
    WITH files AS (
        SELECT body:date::date AS rate_date, body:rates AS rates, landed_at, file_path
        FROM {frankfurter_raw_table}
        WHERE body:base::string = 'USD'
    ),
    rates_exploded AS (
        SELECT rate_date, explode(cast(rates AS MAP<STRING, DOUBLE>)) AS (currency, units_per_usd),
            landed_at, file_path
        FROM files
    ),
    all_rates AS (
        SELECT rate_date, currency, units_per_usd, landed_at, file_path
        FROM rates_exploded
        UNION ALL
        SELECT rate_date, 'USD' AS currency, 1.0D AS units_per_usd, landed_at, file_path
        FROM files
    )
    SELECT rate_date, currency, units_per_usd, 1.0D / units_per_usd AS usd_per_unit, landed_at, file_path
    FROM all_rates
    QUALIFY ROW_NUMBER() OVER (PARTITION BY rate_date, currency ORDER BY landed_at DESC, file_path DESC) = 1
""")

# COMMAND ----------

row_count = spark.table(silver_fx_table).count()
print(f"{silver_fx_table} has {row_count} rows")

display(spark.sql(f"""
    SELECT rate_date, count(*) AS currencies
    FROM {silver_fx_table}
    GROUP BY rate_date
    ORDER BY rate_date DESC
    LIMIT 10
"""))
