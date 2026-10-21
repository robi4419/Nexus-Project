"""Daily ingestion of the Arbeitnow job board feed.

Downloads every job in the feed (a rolling window of about 7 days, mostly on-site jobs in Europe) and saves each API
page, unchanged, to `/Volumes/<catalog>/bronze/landing/arbeitnow/ingest_date=YYYY-MM-DD/run=<run id>/page_NNN.json`.
The client waits 2 seconds between pages, so a run takes about a minute.
"""

import logging
from datetime import datetime, timedelta, timezone

from airflow.sdk import Asset, dag, get_current_context, task
from airflow.timetables.trigger import CronTriggerTimetable

log = logging.getLogger(__name__)

LANDING_ASSET = Asset("landing/arbeitnow")


@dag(
    dag_id="ingest_arbeitnow",
    schedule=CronTriggerTimetable("0 18 * * *", timezone="UTC", run_immediately=True),
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["arbeitnow", "ingestion"],
    doc_md=__doc__,
)
def ingest_arbeitnow():
    @task
    def ensure_landing_volume() -> str:
        """Create the bronze schema and the landing Volume if they don't exist yet."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.landing import LandingVolume, ensure_volume

        return ensure_volume(WorkspaceClient(), LandingVolume.from_env())

    @task(outlets=[LANDING_ASSET])
    def fetch_and_land() -> dict:
        """Fetch every page of the feed and write it to this run's folder in the Volume."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.http import build_session
        from ingestion.common.landing import LandingVolume
        from ingestion.sources.arbeitnow.land import land

        dag_run = get_current_context()["dag_run"]
        summary = land(
            session=build_session(),
            ws=WorkspaceClient(),
            volume=LandingVolume.from_env(),
            run_id=dag_run.run_id,
            run_date=dag_run.run_after,
        )
        log.info("Landed %s jobs in %s pages to %s", summary["jobs"], summary["pages"], summary["folder"])
        return summary

    @task(retries=0)  # re-checking the same summary can't change the result
    def check_run(summary: dict) -> None:
        """Fail the run if nothing was landed."""
        if summary["jobs"] == 0:
            raise ValueError(f"No jobs landed in {summary['folder']}")
        log.info("Run OK: %s", summary)

    volume = ensure_landing_volume()
    summary = fetch_and_land()
    volume >> summary
    check_run(summary)


ingest_arbeitnow()
