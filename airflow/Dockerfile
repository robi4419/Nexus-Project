# Custom Airflow image: official Airflow + Databricks provider + dbt (in its own virtualenv).
# Built from the repo root (see build.context in docker-compose.yaml), so COPY paths are relative to it.
FROM apache/airflow:3.3.2

# Libraries installed into Airflow's own Python environment (what DAGs and tasks import).
COPY airflow/requirements.txt /tmp/airflow-requirements.txt
RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt

# dbt gets a separate virtualenv because its dependencies conflict with Airflow's.
# Tasks call it by path: /opt/dbt-venv/bin/dbt
USER root
COPY dbt/requirements.txt /tmp/dbt-requirements.txt
RUN python -m venv /opt/dbt-venv \
    && /opt/dbt-venv/bin/pip install --no-cache-dir -r /tmp/dbt-requirements.txt \
    && rm /tmp/dbt-requirements.txt /tmp/airflow-requirements.txt
USER airflow
