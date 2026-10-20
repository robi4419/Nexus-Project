"""Daily ECB exchange rates from the Frankfurter API.

Each run fetches the USD-based rates for **its own date** and saves the API response, unchanged, to
`/Volumes/<catalog>/bronze/landing/frankfurter/ingest_date=YYYY-MM-DD/run=<run id>/rates.json`.

`catchup=True`: unpausing backfills every weekday since `start_date`, and weekdays missed while
Airflow was off are filled in automatically when it starts again.
"""

import logging
from datetime import datetime, timedelta, timezone

from airflow.sdk import Asset, dag, get_current_context, task
from airflow.timetables.trigger import CronTriggerTimetable

log = logging.getLogger(__name__)

LANDING_ASSET = Asset("landing/frankfurter")
MIN_CURRENCIES = 20


@dag(
    dag_id="ingest_fx_rates",
    schedule=CronTriggerTimetable("0 17 * * 1-5", timezone="UTC"),
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=True,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=10)},
    tags=["fx", "ingestion"],
    doc_md=__doc__,
)
def ingest_fx_rates():
    @task
    def ensure_landing_volume() -> str:
        """Create the bronze schema and the landing Volume if they don't exist yet."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.landing import LandingVolume, ensure_volume

        return ensure_volume(WorkspaceClient(), LandingVolume.from_env())

    @task(outlets=[LANDING_ASSET])
    def fetch_and_land() -> dict:
        """Fetch the rates for this run's date and write them to this run's folder in the Volume."""
        from databricks.sdk import WorkspaceClient

        from ingestion.common.http import build_session
        from ingestion.common.landing import LandingVolume
        from ingestion.sources.frankfurter.land import land

        dag_run = get_current_context()["dag_run"]
        summary = land(
            session=build_session(),
            ws=WorkspaceClient(),
            volume=LandingVolume.from_env(),
            run_id=dag_run.run_id,
            run_date=dag_run.run_after,
        )
        log.info(
            "Landed %s rates for %s (ECB date %s) to %s",
            len(summary["currencies"]),
            summary["requested_date"],
            summary["rate_date"],
            summary["folder"],
        )
        return summary

    @task(retries=0)  # re-checking the same summary can't change the result
    def check_run(summary: dict) -> None:
        """Fail the run if the rates look incomplete."""
        currencies = summary["currencies"]
        if len(currencies) < MIN_CURRENCIES or "EUR" not in currencies:
            raise ValueError(f"Expected at least {MIN_CURRENCIES} currencies including EUR, got {currencies}")
        log.info("Run OK: %s", summary)

    volume = ensure_landing_volume()
    summary = fetch_and_land()
    volume >> summary
    check_run(summary)


ingest_fx_rates()
