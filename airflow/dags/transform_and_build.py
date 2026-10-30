"""Turn the day's landed files into silver and gold: the Databricks Job `transform_jobs`, then dbt.

Runs once all three job sources have landed a checked run since this DAG last ran (Assets `landing/jobicy`,
`landing/arbeitnow` and `landing/himalayas`), normally about 15 minutes after the 18:00 UTC ingestion. Exchange rates
aren't a condition: silver uses the latest rate on or before each job's date.

1. `run_transform_job` starts the Databricks Job (bronze, silver, checks) and waits for it in the triggerer.
2. `dbt_deps`, `dbt_source_freshness` and `dbt_build` rebuild gold with the dbt virtualenv in the image.

Every step is idempotent, so a retry or a manual run is safe. A manual run is also how to catch up after a failure.
"""

import os
from datetime import datetime, timedelta, timezone

from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator
from airflow.sdk import Asset, dag, task

# The development-mode Job name carries the user name, so it comes from .env (decision 7 in the Phase 4 plan).
TRANSFORM_JOB_NAME = os.environ.get("DATABRICKS_TRANSFORM_JOB_NAME")
if not TRANSFORM_JOB_NAME:
    raise RuntimeError("DATABRICKS_TRANSFORM_JOB_NAME is not set: add it to the root .env and recreate the containers")

# dbt has its own virtualenv in the image (airflow/Dockerfile); DBT_PROJECT_DIR, DBT_PROFILES_DIR and the /tmp target
# and log paths come from docker-compose. --no-use-colors keeps colour codes out of the task logs.
DBT = "/opt/dbt-venv/bin/dbt --no-use-colors"


@dag(
    dag_id="transform_and_build",
    schedule=(Asset("landing/jobicy") & Asset("landing/arbeitnow") & Asset("landing/himalayas")),
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    max_active_runs=1,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["databricks", "dbt", "transform"],
    doc_md=__doc__,
)
def transform_and_build():
    # Deferrable: while the Job runs, the triggerer polls it every 30 seconds and no worker slot is held.
    run_transform_job = DatabricksRunNowOperator(
        task_id="run_transform_job",
        job_name=TRANSFORM_JOB_NAME,
        deferrable=True,
        execution_timeout=timedelta(hours=1),
    )

    @task.bash(execution_timeout=timedelta(minutes=10))
    def dbt_deps() -> str:
        """Install the dbt packages pinned in package-lock.yml (dbt_utils), in case they're missing."""
        return f"{DBT} deps"

    @task.bash(execution_timeout=timedelta(minutes=10))
    def dbt_source_freshness() -> str:
        """Fail if silver.jobs wasn't rebuilt within 2 days: guards against a Job that succeeded without rebuilding."""
        return f"{DBT} source freshness"

    @task.bash(execution_timeout=timedelta(minutes=30))
    def dbt_build() -> str:
        """Build gold: the seed, every model and every test, in dependency order."""
        return f"{DBT} build"

    run_transform_job >> dbt_deps() >> dbt_source_freshness() >> dbt_build()


transform_and_build()
