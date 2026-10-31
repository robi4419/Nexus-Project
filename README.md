# Nexus-Project

A daily data pipeline for the remote job market. It collects job postings from Jobicy, Arbeitnow and Himalayas, plus ECB exchange rates. It cleans them, extracts the skills and tools each posting asks for, and builds a star schema for dashboards you can filter by country, industry, seniority, job type and date.

**Stack:** Apache Airflow 3 (orchestration, in Docker) · Databricks (bronze and silver: Auto Loader, PySpark, Unity Catalog) · dbt (the gold star schema, with contracts and tests) · Power BI (dashboards) · GitHub Actions (CI)

See [docs/PLAN.md](docs/PLAN.md) for the architecture and the development plan, and [`docs/phases/`](docs/phases/) for each phase's decisions.

## How it runs

Every evening, with no manual step:

```
18:00 UTC  ingest_jobicy ───────┐
18:00 UTC  ingest_arbeitnow ────┼─ raw JSON in a Unity Catalog Volume ─►  transform_and_build
18:00 UTC  ingest_himalayas ────┘  (once all three have landed)              Databricks Job transform_jobs:
17:00 UTC  ingest_fx_rates (weekdays)                                          bronze (Auto Loader) → silver
                                                                               (clean, dedupe, locations, salaries
                                                                               in USD, skills) → data-quality checks
                                                                             dbt: deps → source freshness → build
                                                                               (gold star schema and its tests)
any failed run ─► email
```

## Data sources and credits

- Job postings from [Jobicy](https://jobicy.com), [Arbeitnow](https://www.arbeitnow.com) and [Himalayas](https://himalayas.app). Data sourced from Himalayas is credited with a link. Every Apply link goes to the original posting, through Himalayas' `applicationLink` for its jobs, and Himalayas jobs are deleted once they expire, as its API terms require.
- Exchange rates from the European Central Bank, via [Frankfurter](https://frankfurter.dev).
- City names from [GeoNames](https://www.geonames.org) (CC BY 4.0).

## Repository layout

| Path | Contents |
|---|---|
| `airflow/` | Airflow image (`Dockerfile`), DAGs, plugins (failure emails) and config |
| `ingestion/` | API clients that write each source's raw responses to the landing Volume |
| `transform/` | Plain-Python logic for silver: HTML to text, seniority, locations, skills, and the Tech title rules that Himalayas landing also uses |
| `databricks/` | Asset Bundle Job definition, notebooks (bronze, silver, checks) and reference CSVs |
| `databricks.yml` | Asset Bundle root |
| `dbt/job_listings/` | dbt project for the gold layer ([its README](dbt/job_listings/README.md)) |
| `dashboards/` | Power BI project |
| `scripts/` | One-off helpers: build the GeoNames reference data, export the marts' DDL for the ER diagram |
| `tests/` | pytest suite |
| `docs/` | Plan, per-phase docs and the ER diagram |
| `docker-compose.yaml` | Local Airflow stack (Postgres, Redis, scheduler, worker, API server, …) |

## Getting started

**Prerequisites:**
- Docker Desktop with at least 4 GB of RAM allocated;
- Python 3.12 or later;
- the Databricks CLI;
- a Databricks workspace (Free Edition works) with a SQL warehouse and a personal access token;
- a free Himalayas API key;
- a Gmail address with an app password, for failure emails.

1. Copy `.env.example` to `.env` and fill in the values. `.env` is gitignored; never commit it.
2. Create the local virtualenv for tests and dbt development:
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
3. Log the Databricks CLI in with `databricks configure`, which saves the profile in your home folder, outside the repo. Then deploy the Job:
   ```
   databricks bundle deploy
   ```
   Copy the Job's name, `[dev <you>] transform_jobs`, into `.env` as `DATABRICKS_TRANSFORM_JOB_NAME`.
4. Build and start Airflow from the repo root:
   ```
   docker compose build
   docker compose up -d
   ```
5. Open http://localhost:8080 (user `airflow`, password `airflow`) and unpause:
   - `ingest_jobicy`, `ingest_arbeitnow`, `ingest_himalayas`;
   - `ingest_fx_rates`, which backfills its weekdays since 2026-10-01;
   - `transform_and_build`.

   From then on, everything runs by itself every day. Trigger `alert_test` once to check that failure emails arrive.
6. Optional: `docker compose --profile flower up -d` starts the Celery monitor at http://localhost:5555.

Stop everything with `docker compose down`. Airflow runs only while Docker is up, and runs missed while it was down start when it comes back.

## Development

- **Tests:** `.venv\Scripts\python.exe -m pytest`.
- **dbt by hand:** see the [dbt README](dbt/job_listings/README.md).
- **After changing notebooks, reference CSVs or `transform/`,** run `databricks bundle deploy`. Airflow reads `ingestion/` and `transform/` live from the mounted folders; Databricks uses the deployed copy.
