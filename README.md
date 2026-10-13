# Nexus-Project

Pulls remote job postings from the [Jobicy API](https://jobicy.com), extracts the skills and technologies each posting asks for, and turns them into dashboards you can filter by country, industry, seniority and date.

**Stack:** Apache Airflow (orchestration, in Docker) · Databricks (storage, cleaning, skill extraction, dashboards) · dbt (analytical models) · GitHub Actions (CI)

See [docs/PLAN.md](docs/PLAN.md) for the architecture and development plan.

Job data courtesy of [Jobicy](https://jobicy.com); each posting links back to its original listing.

## Repository layout

| Path | Contents |
|---|---|
| `docker-compose.yaml` | Local Airflow stack (Postgres, Redis, scheduler, worker, API server, ...) |
| `airflow/` | Airflow image (`Dockerfile`), DAGs, plugins, config |
| `ingestion/` | Python code that fetches postings from Jobicy |
| `databricks/` | Databricks notebooks and jobs (bronze/silver layers) |
| `dbt/job_listings/` | dbt project (gold layer) |
| `dashboards/` | Exported Databricks dashboards |
| `docs/` | Plan and per-phase docs |

## Getting started

**Prerequisites:** Docker Desktop (≥4 GB RAM allocated), Python 3.12+, a Databricks workspace with a SQL warehouse and a personal access token.

1. Copy `.env.example` to `.env` and fill in the values.
2. Build and start Airflow from the repo root:
   ```
   docker compose build
   docker compose up -d
   ```
3. Open http://localhost:8080 (user `airflow`, password `airflow`).
4. Optional: `docker compose --profile flower up -d` for the Celery monitor at http://localhost:5555.

Stop everything with `docker compose down`.

### Running dbt locally

```
python -m venv .venv
.venv\Scripts\activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cd dbt/job_listings
dbt debug                       # needs the DATABRICKS_* variables from .env in your environment
```
