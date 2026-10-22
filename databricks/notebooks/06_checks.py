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

from datetime import datetime, timezone

dbutils.widgets.text("catalog", "workspace")
catalog = dbutils.widgets.get("catalog")

bronze = f"{catalog}.bronze"
silver = f"{catalog}.silver"
SOURCES = ["jobicy", "arbeitnow", "himalayas"]

checks = []  # (level, name, sql), shown in this order


def check(level: str, name: str, sql: str) -> None:
    """Register a check. Its SQL must return one row with the columns `value` and `passed`."""
    assert level in ("error", "warning", "info"), f"unknown level {level!r}"
    checks.append((level, name, sql))


def share_by_source(hit: str, join: str = "") -> str:
    """SQL for an info check: the share of each source's jobs (alias j) where `hit` is true, after an optional join,
    shown as e.g. 'arbeitnow 36.4% (2119 of 5824), himalayas 0.0% (0 of 1442), jobicy 0.0% (0 of 1875)'."""
    return f"""
        SELECT array_join(sort_array(collect_list(
                   format_string('%s %.1f%% (%d of %d)', source, 100 * hits / jobs, hits, jobs))), ', ') AS value,
               true AS passed
        FROM (
            SELECT j.source, count(*) AS jobs, count_if({hit}) AS hits
            FROM {silver}.jobs AS j
            {join}
            GROUP BY j.source
        )
    """


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

# Per source: silver jobs / distinct jobs in bronze. A Himalayas job counts only while its latest copy hasn't expired.
check(
    "error",
    "jobs: silver job count equals distinct jobs in bronze, per source",
    f"""
    WITH jobicy AS (
        SELECT landed_at, explode(cast(body:jobs AS ARRAY<VARIANT>)) AS job FROM {bronze}.jobicy_raw
    ),
    arbeitnow AS (
        SELECT landed_at, explode(cast(body:data AS ARRAY<VARIANT>)) AS job FROM {bronze}.arbeitnow_raw
    ),
    himalayas AS (
        SELECT landed_at, explode(cast(body:jobs AS ARRAY<VARIANT>)) AS job FROM {bronze}.himalayas_raw
    ),
    bronze_jobs AS (
        SELECT 'jobicy' AS source, job:id::STRING AS source_job_id, landed_at, CAST(NULL AS TIMESTAMP) AS expires_at
        FROM jobicy
        UNION ALL
        SELECT 'arbeitnow', job:slug::STRING, landed_at, NULL FROM arbeitnow
        UNION ALL
        SELECT 'himalayas', job:guid::STRING, landed_at, timestamp_seconds(job:expiryDate::BIGINT) FROM himalayas
    ),
    bronze_counts AS (
        SELECT source, count_if(latest_expiry IS NULL OR latest_expiry > current_timestamp()) AS in_bronze
        FROM (
            SELECT source, source_job_id, max_by(expires_at, landed_at) AS latest_expiry
            FROM bronze_jobs
            GROUP BY source, source_job_id
        )
        GROUP BY source
    ),
    silver_counts AS (
        SELECT source, count(*) AS in_silver FROM {silver}.jobs GROUP BY source
    )
    SELECT
        array_join(sort_array(collect_list(
            format_string('%s %d/%d', b.source, coalesce(s.in_silver, 0), b.in_bronze))), ', ') AS value,
        bool_and(coalesce(s.in_silver, 0) = b.in_bronze) AS passed
    FROM bronze_counts AS b
    LEFT JOIN silver_counts AS s ON s.source = b.source
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

# Jobicy and Himalayas use fixed lists of places, so an unknown one means a gap in locations.csv or countries.csv.
# Arbeitnow's free text has its own warning below.
check(
    "error",
    "job_locations: no unknown Jobicy or Himalayas locations",
    f"""
    SELECT count_if(location_type = 'unknown') AS value, value = 0 AS passed
    FROM {silver}.job_locations
    WHERE source IN ('jobicy', 'himalayas')
    """,
)

# API terms (Phase 2b, decisions 18, 20 and 22): no expired Himalayas job in silver, and no expired row in bronze.
check(
    "error",
    "jobs: no expired Himalayas job",
    f"""
    SELECT count(*) AS value, value = 0 AS passed
    FROM {silver}.jobs
    WHERE source = 'himalayas' AND (expires_at IS NULL OR expires_at <= current_timestamp())
    """,
)

# The retention task deletes rows expiring by tomorrow; this checks the stricter minimum, nothing expiring today or
# earlier, so a run that crosses midnight UTC can't fail it by accident. A row without an expiry day fails it too.
today = datetime.now(timezone.utc).date().isoformat()
expiry_day = "regexp_extract(file_path, 'expires_([0-9]{4}-[0-9]{2}-[0-9]{2})[.]json$', 1)"
check(
    "error",
    "bronze: no expired Himalayas row",
    f"""
    SELECT count_if({expiry_day} = '' OR {expiry_day} <= '{today}') AS value, value = 0 AS passed
    FROM {bronze}.himalayas_raw
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

for source in SOURCES:
    check(
        "warning",
        f"bronze: newest {source} file landed less than 2 days ago",
        f"""
        SELECT max(landed_at) AS value, value >= current_timestamp() - INTERVAL 2 DAYS AS passed
        FROM {bronze}.{source}_raw
    """,
    )

# Arbeitnow locations are free text: 4.5% of sampled jobs had an unknown one, 2.6 points of them empty (decision 15).
check(
    "warning",
    "job_locations: at most 10% of Arbeitnow jobs have an unknown location",
    f"""
    SELECT
        -- try_divide gives NULL (shown as WARN) instead of an error when there are no Arbeitnow rows at all
        try_divide(
            count(DISTINCT CASE WHEN location_type = 'unknown' THEN source_job_id END),
            count(DISTINCT source_job_id)
        ) AS share,
        format_string('%.1f%%', 100 * share) AS value,
        share <= 0.10 AS passed
    FROM {silver}.job_locations
    WHERE source = 'arbeitnow'
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

def found_in(table: str) -> str:
    """A LEFT JOIN to the jobs that have at least one row in a bridge table; `x.found` is NULL for the others."""
    return f"""
        LEFT JOIN (SELECT DISTINCT source, source_job_id, true AS found FROM {silver}.{table}) AS x
            ON x.source = j.source AND x.source_job_id = j.source_job_id
    """


check("info", "job_skills: share of jobs with at least 1 skill", share_by_source("x.found", found_in("job_skills")))
check("info", "jobs: share with seniority Unspecified", share_by_source("j.seniority = 'Unspecified'"))
# Expected by design for Arbeitnow (decisions 12 and 13): company-specific tags and contract-only job types map to
# nothing.
check("info", "jobs: share without an industry", share_by_source("x.found IS NULL", found_in("job_industries")))
check("info", "jobs: share without a job type", share_by_source("x.found IS NULL", found_in("job_types")))

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
