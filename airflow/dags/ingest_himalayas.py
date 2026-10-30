"""Daily ingestion of new and updated Tech jobs from the Himalayas remote jobs feed.

Walks the feed newest first back to the previous run's newest job minus a day (2 days on the first run), keeps the
Tech categories, and writes them, one file per expiry day, to
`/Volumes/<catalog>/bronze/landing/himalayas/ingest_date=YYYY-MM-DD/run=<run id>/expires_YYYY-MM-DD.json`, plus a
`manifest.json` that tells the next run where to stop. Needs `HIMALAYAS_API_KEY` in the root `.env`.

API terms: every Apply uses `applicationLink`, the dashboards credit Himalayas with a link, the jobs aren't passed
on, and jobs are removed once they expire: `purge_expired` deletes landed files whose expiry day is tomorrow or
earlier, every run (bronze is purged in Databricks, Phase 2b, 2b.9).
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from airflow.sdk import Asset, dag, get_current_context, task
from airflow.timetables.trigger import CronTriggerTimetable

log = logging.getLogger(__name__)

LANDING_ASSET = Asset("landing/himalayas")


@dag(
    dag_id="ingest_himalayas",
    schedule=CronTriggerTimetable("0 18 * * *", timezone="UTC", run_immediately=True),
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["himalayas", "ingestion"],
    doc_md=__doc__,
)
def ingest_himalayas():
    @task
    def ensure_landing_volume() -> str:
        """Create the bronze schema and the landing Volume if they don't exist yet."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.landing import LandingVolume, ensure_volume

        return ensure_volume(WorkspaceClient(), LandingVolume.from_env())

    @task
    def fetch_and_land() -> dict:
        """Fetch the jobs updated since the cutoff and write the Tech ones, then the manifest, to this run's folder."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.http import build_session
        from ingestion.common.landing import LandingVolume
        from ingestion.sources.himalayas.land import land

        api_key = os.environ.get("HIMALAYAS_API_KEY")
        if not api_key:
            raise RuntimeError("HIMALAYAS_API_KEY is not set: add it to the root .env and recreate the containers")

        dag_run = get_current_context()["dag_run"]
        summary = land(
            # Deep pages sometimes answer 503 for a minute or more: 8 retries wait about 6 minutes in total.
            session=build_session(retries=8),
            ws=WorkspaceClient(),
            volume=LandingVolume.from_env(),
            api_key=api_key,
            run_id=dag_run.run_id,
            run_date=dag_run.run_after,
        )
        log.info(
            "Landed %s Tech jobs of %s seen (%s pages, cutoff %s from %s) to %s",
            summary["tech_jobs"], summary["jobs_seen"], summary["pages"], summary["cutoff"], summary["cutoff_from"],
            summary["folder"],
        )
        return summary

    @task
    def purge_expired() -> dict:
        """Delete the landed job files whose jobs expire by tomorrow. Runs even when fetching fails."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.landing import LandingVolume
        from ingestion.sources.himalayas import land

        summary = land.purge_expired(WorkspaceClient(), LandingVolume.from_env())
        log.info("Purge: %s", summary)
        return summary

    # The Asset is updated only once the run is checked, so transform_and_build never starts on a bad landing.
    @task(outlets=[LANDING_ASSET], retries=0)  # re-checking the same summary can't change the result
    def check_run(summary: dict) -> None:
        """Fail the run if the feed returned nothing, or no Tech jobs: the cutoff always covers at least a day, so
        zero Tech jobs would mean Himalayas renamed its categories."""
        if summary["jobs_seen"] == 0:
            raise ValueError(f"The feed returned no jobs (cutoff {summary['cutoff']})")
        if summary["tech_jobs"] == 0:
            raise ValueError(f"No Tech jobs among {summary['jobs_seen']}: have the parentCategories changed?")
        log.info("Run OK: %s", summary)

    volume = ensure_landing_volume()
    summary = fetch_and_land()
    volume >> [summary, purge_expired()]
    check_run(summary)


ingest_himalayas()
