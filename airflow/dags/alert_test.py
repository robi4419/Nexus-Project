"""Manual check that failure emails arrive: its only task fails on purpose.

Trigger it after setting up or changing the Gmail app password (`SMTP_PASSWORD` in `.env`): within a minute or two an
email "Airflow: alert_test failed" should reach `ALERT_EMAIL`. It has no schedule, so it never runs by itself.
"""

from datetime import datetime, timezone

from airflow.sdk import dag, task

from pipeline_alerts import failure_email  # airflow/plugins/pipeline_alerts.py


@dag(
    dag_id="alert_test",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    on_failure_callback=failure_email(),
    tags=["alerts"],
    doc_md=__doc__,
)
def alert_test():
    @task(retries=0)
    def fail_on_purpose() -> None:
        """Fail, so the DAG run fails and its failure callback sends the email."""
        raise RuntimeError("This task fails on purpose, to test the failure email.")

    fail_on_purpose()


alert_test()
