"""Failure emails: one per failed DAG run, sent through the `smtp_default` connection (Gmail, see docker-compose.yaml).

Every DAG sets `on_failure_callback=failure_email()`. A DAG-level callback runs once the run has failed for good,
after its tasks' retries, and it runs in the DAG processor, which has the same environment as the workers.

It lives in airflow/plugins/ because Airflow 3 puts the plugins folder (not the DAG folder) on Python's import path in
every Airflow process; the plugin loader imports it at startup, finds no plugin in it, and leaves it alone.
"""

import logging
import os

from airflow.providers.smtp.notifications.smtp import SmtpNotifier

log = logging.getLogger(__name__)

# The Airflow UI as seen from the host (docker-compose publishes the API server on port 8080).
AIRFLOW_UI = "http://localhost:8080"

SUBJECT = "Airflow: {{ dag_run.dag_id }} failed"
BODY = f"""
<p>The DAG run <b>{{{{ dag_run.run_id }}}}</b> of <b>{{{{ dag_run.dag_id }}}}</b> failed.</p>
<p>Reason: {{{{ reason }}}}</p>
<p><a href="{AIRFLOW_UI}/dags/{{{{ dag_run.dag_id }}}}/runs/{{{{ dag_run.run_id | urlencode }}}}">Open the run in Airflow</a>
(the PC and Docker must be on) and read the failed task's log.</p>
"""


def failure_email() -> SmtpNotifier | None:
    """A new notifier for a DAG's on_failure_callback, or None (no emails) when ALERT_EMAIL isn't set.

    Each DAG gets its own instance, because a notifier renders its templates onto itself when it fires.
    """
    to = os.environ.get("ALERT_EMAIL")
    if not to:
        log.warning("ALERT_EMAIL is not set: failure emails are off")
        return None
    return SmtpNotifier(to=to, subject=SUBJECT, html_content=BODY, smtp_conn_id="smtp_default")
