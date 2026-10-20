# Databricks notebook source
# MAGIC %md
# MAGIC # Data-quality checks
# MAGIC
# MAGIC Runs every check below against the bronze and silver tables and shows one results table. Each check is one SQL
# MAGIC query that returns a single row with two columns: `value` (what to show) and `passed` (true or false).
# MAGIC
# MAGIC - **error**: a failed error check fails this task, and so the Job run. The tables are already written; the red
# MAGIC   run is the alert.
# MAGIC - **warning**: shown as `WARN` when it doesn't pass, but never fails the run.
# MAGIC - **info**: a number to watch over time, with no target; its query returns `true AS passed`.
# MAGIC
# MAGIC A check whose query itself fails counts as failed. Parameters: `catalog` (e.g. `workspace`).

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")

bronze = f"{catalog}.bronze"
silver = f"{catalog}.silver"

checks = []  # (level, name, sql), shown in this order


def check(level: str, name: str, sql: str) -> None:
    """Register a check. Its SQL must return one row with the columns `value` and `passed`."""
    assert level in ("error", "warning", "info"), f"unknown level {level!r}"
    checks.append((level, name, sql))


# COMMAND ----------

# MAGIC %md
# MAGIC ## Errors

# COMMAND ----------

check(
    "error",
    "jobs: one row per (source, source_job_id)",
    f"""
    SELECT count(*) - count(DISTINCT source, source_job_id) AS value, value = 0 AS passed
    FROM {silver}.jobs
""",
)

check(
    "error",
    "jobs: required fields are filled",
    f"""
    SELECT count_if(title IS NULL OR url IS NULL OR published_at IS NULL OR company_name IS NULL) AS value, value = 0 AS passed
    FROM {silver}.jobs
    """,
)

check(
    "error",
    "jobs: silver job count equals distinct jobs in bronze",
    f"""
    WITH bronze_jobs_variants AS (
        SELECT run_id, landed_at, EXPLODE(cast(body:jobs AS ARRAY<VARIANT>)) as job
        FROM {bronze}.jobicy_raw
    )
    SELECT 
        (SELECT count(DISTINCT job:id::string) FROM bronze_jobs_variants) AS bronze_jobs,
        (SELECT count(*) FROM {silver}.jobs) AS silver_jobs,
        concat(silver_jobs, '/', bronze_jobs) AS value,
        silver_jobs = bronze_jobs as passed
""",
)

check(
    "error",
    "job_locations: every job has a location",
    f"""
    SELECT count(*) AS value, value = 0 AS passed
    FROM {silver}.jobs
    LEFT ANTI JOIN {silver}.job_locations USING(source, source_job_id)
    """,
)

check(
    "error",
    "job_locations: no unknown locations",
    f"""
    SELECT count_if(location_type = 'unknown') AS value, value = 0 AS passed
    FROM {silver}.job_locations
    """,
)

check(
    "error",
    "job_skills: every skill exists in ref_skills",
    f"""
    SELECT count(*) AS value, value = 0 AS passed
    FROM {silver}.job_skills
    LEFT ANTI JOIN {silver}.ref_skills USING(skill)
    """,
)

check(
    "error",
    "job_skills: same taxonomy_version as ref_skills",
    f"""
    WITH unified_taxonomy AS (
        SELECT taxonomy_version FROM {silver}.job_skills
        UNION ALL
        SELECT taxonomy_version FROM {silver}.ref_skills
    )
    SELECT count(DISTINCT taxonomy_version) AS value, value = 1 AS passed
    FROM unified_taxonomy
    """,
)

check(
    "error",
    "fx_rates: every entry is unique per (rate_date, currency)",
    f"""
    SELECT count(*) - count(DISTINCT rate_date, currency) AS value, value = 0 AS passed
    FROM {silver}.fx_rates
    """,
)

check(
    "error",
    "fx_rates: USD = 1 on every date",
    f"""
    SELECT count(DISTINCT rate_date) - count_if(currency = 'USD' AND units_per_usd = 1) AS value, value = 0 AS passed
    FROM {silver}.fx_rates
    """,
)

for table in ["job_industries", "job_types", "job_locations", "job_skills"]:
    check(
        "error",
        f"{table}: every row belongs to a job",
        f"""
        SELECT count(*) as value, value = 0 as passed
        FROM {silver}.{table}
        LEFT ANTI JOIN {silver}.jobs USING(source, source_job_id)
        """,
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Warnings

# COMMAND ----------

check(
    "warning",
    "bronze: newest Jobicy file landed less than 2 days ago",
    f"""
    SELECT max(landed_at) AS value, value >= current_timestamp() - INTERVAL 2 DAYS AS passed
    FROM {bronze}.jobicy_raw
""",
)

check(
    "warning",
    "job_skills: Software Engineering skill coverage of at least 90%",
    f"""
    WITH se_jobs AS (
        SELECT DISTINCT source, source_job_id FROM {silver}.job_industries WHERE industry = 'Software Engineering'
    ),
    jobs_with_skills AS (
        SELECT DISTINCT source, source_job_id FROM {silver}.job_skills
    )
    SELECT count(w.source_job_id) / count(*) AS share,
        round(100 * share, 1) || '%' AS value,
        share >= 0.9 AS passed
    FROM se_jobs AS s
    LEFT JOIN jobs_with_skills AS w ON s.source = w.source AND s.source_job_id = w.source_job_id
""",
)

# A salary without any USD value, split by why: no currency given, no exchange rate for the currency
# (e.g. BGN, which the ECB no longer publishes), or a rate was found but the period text is unknown.
check(
    "warning",
    "jobs: every salary has a USD value",
    f"""
    SELECT
        count_if(salary_currency IS NULL) AS no_currency,
        count_if(salary_currency IS NOT NULL AND fx_rate_date IS NULL) AS no_rate,
        count_if(fx_rate_date IS NOT NULL) AS unknown_period,
        format_string('no currency %d, no rate %d, unknown period %d', no_currency, no_rate, unknown_period) AS value,
        no_currency + no_rate + unknown_period = 0 AS passed
    FROM {silver}.jobs
    WHERE (salary_min IS NOT NULL OR salary_max IS NOT NULL)
      AND salary_min_usd_yearly IS NULL
      AND salary_max_usd_yearly IS NULL
""",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Info

# COMMAND ----------

check(
    "info",
    "job_skills: share of jobs with at least 1 skill",
    f"""
    SELECT
        (SELECT count(DISTINCT source, source_job_id) FROM {silver}.job_skills) AS with_skills,
        (SELECT count(*) FROM {silver}.jobs) AS all_jobs,
        format_string('%.1f%% (%d of %d jobs)', 100 * with_skills / all_jobs, with_skills, all_jobs) AS value,
        true AS passed
""",
)

check(
    "info",
    "jobs: share with seniority Unspecified",
    f"""
    SELECT
        count_if(seniority = 'Unspecified') AS unspecified,
        count(*) AS all_jobs,
        format_string('%.1f%% (%d of %d jobs)', 100 * unspecified / all_jobs, unspecified, all_jobs) AS value,
        true AS passed
    FROM {silver}.jobs
""",
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run all checks

# COMMAND ----------

results = []
for level, name, sql in checks:
    try:
        row = spark.sql(sql).first()
        # A NULL `passed` (e.g. max() over an empty table) counts as not passed.
        value, passed = str(row["value"]), bool(row["passed"])
    except Exception as error:
        # A broken query is reported as a failed check instead of stopping the others.
        value, passed = f"query failed: {str(error).splitlines()[0][:200]}", False
    if level == "info":
        status = "INFO"
    else:
        status = "PASS" if passed else {"error": "FAIL", "warning": "WARN"}[level]
    results.append((level, name, value, status))

display(spark.createDataFrame(results, ["level", "check", "value", "status"]))

failed = [name for level, name, value, status in results if status == "FAIL"]
if failed:
    raise Exception(f"{len(failed)} error check(s) failed: " + "; ".join(failed))
print(f"All {sum(level == 'error' for level, *_ in results)} error checks passed.")
