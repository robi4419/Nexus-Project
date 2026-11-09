# Nexus-Project

A daily data pipeline for the remote job market. It collects job postings from Jobicy, Arbeitnow and Himalayas, plus ECB exchange rates. It cleans them, extracts the skills and tools each posting asks for, and builds a star schema for a Power BI report you can filter by country, industry, seniority, job type and date.

**Live report:** https://robi4419.github.io/Nexus-Project/, with four pages (skills overview, rising skills, salaries, skills asked together), refreshed every night.

![The tech stack: public APIs send JSON over HTTPS to Apache Airflow 3 (Python, requests, the Databricks SDK and provider), which runs in Docker Compose with Celery, Redis and PostgreSQL. Airflow writes raw files to a Unity Catalog volume, runs a Databricks Job whose Apache Spark notebooks (PySpark, Auto Loader) write Delta Lake tables, and runs dbt Core (dbt-databricks, dbt_utils, Jinja), which sends SQL to a serverless SQL warehouse. The Power BI service in a Microsoft 365 tenant imports from it, Power BI Desktop publishes to it, and the report is embedded in a GitHub Pages site. GitHub holds the code and the GeoNames cities, provides the Docker image and DAGs, deploys the Databricks Asset Bundle, and GitHub Actions deploys the site. Failed tasks alert through Gmail; development uses pytest, python-dotenv and DrawDB.](docs/tech-stack.svg)

**Stack:** Apache Airflow 3 (orchestration, in Docker) · Databricks (bronze and silver: Auto Loader, PySpark, Unity Catalog) · dbt (the gold star schema, with contracts and tests) · Power BI (the report, published to the web) · GitHub Pages and Actions

See [docs/PLAN.md](docs/PLAN.md) for the architecture and the development plan, and [`docs/phases/`](docs/phases/) for each phase's decisions.

## How it runs

Every evening, with no manual step:

![How Nexus-Project works, step by step: one Airflow DAG per source (running in Docker) lands raw JSON in a Databricks volume; once all three job sources have landed, transform_and_build runs the Databricks Job (bronze with Auto Loader, then silver in PySpark, then checks), a dbt source freshness check and dbt build (staging, intermediate, marts and history: gold). The Power BI service refreshes its model from gold at 19:00 UTC, and the report is published to the web and embedded in a GitHub Pages site.](docs/architecture.svg)

## Data sources and credits

- Job postings from [Jobicy](https://jobicy.com), [Arbeitnow](https://www.arbeitnow.com) and [Himalayas](https://himalayas.app). Data sourced from Himalayas is credited with a link. Every Apply link goes to the original posting, through Himalayas' `applicationLink` for its jobs, and Himalayas jobs are deleted once they expire, as its API terms require. The public report shows aggregates only.
- Exchange rates from the European Central Bank, via [Frankfurter](https://frankfurter.dev).
- City names from [GeoNames](https://www.geonames.org) (CC BY 4.0).
- Logos in the architecture diagram from [Simple Icons](https://simpleicons.org) (CC0). The trademarks belong to their owners.

## Repository layout

| Path | Contents |
|---|---|
| `airflow/` | Airflow image (`Dockerfile`), DAGs, plugins (failure emails) and config |
| `ingestion/` | API clients that write each source's raw responses to the landing Volume |
| `transform/` | Plain-Python logic for silver: HTML to text, seniority, locations, skills, and the Tech title rules that Himalayas landing also uses |
| `databricks/` | Asset Bundle Job definition, notebooks (bronze, silver, checks) and reference CSVs |
| `databricks.yml` | Asset Bundle root |
| `dbt/job_listings/` | dbt project for the gold layer ([its README](dbt/job_listings/README.md)) |
| `dashboards/` | Power BI project (PBIP): the semantic model in TMDL and the report pages in PBIR ([Phase 5](docs/phases/phase-5-dashboards.md)) |
| `site/` | The GitHub Pages page that embeds the published report |
| `.github/workflows/` | Deploys `site/` to GitHub Pages on a push to `main` |
| `scripts/` | One-off helpers: build the GeoNames reference data, export the marts' DDL for the ER diagram |
| `tests/` | pytest suite |
| `docs/` | Plan, per-phase docs, the ER diagram, and the tech-stack and step-by-step diagrams (`tech-stack.svg`, `architecture.svg`) |
| `docker-compose.yaml` | Local Airflow stack (Postgres, Redis, scheduler, worker, API server, …) |

## Getting started

**Prerequisites:**
- Docker Desktop with at least 4 GB of RAM allocated;
- Python 3.12 or later;
- the Databricks CLI;
- a Databricks workspace (Free Edition works) with a SQL warehouse and a personal access token;
- a free Himalayas API key;
- a Gmail address with an app password, for failure emails;
- for the report: Power BI Desktop (free, Windows).

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
7. Optional, the report: open `dashboards/JobsAnalytics.pbip` in Power BI Desktop. Point the `DatabricksHost` and `DatabricksHttpPath` parameters at your workspace (Transform data → Edit parameters), refresh, and enter a Databricks access token as the Account key when asked. Publishing it to the web is in [Phase 5, section 5.6](docs/phases/phase-5-dashboards.md).

Stop everything with `docker compose down`. Airflow runs only while Docker is up, and runs missed while it was down start when it comes back.

## Development

- **Tests:** `.venv\Scripts\python.exe -m pytest`.
- **dbt by hand:** see the [dbt README](dbt/job_listings/README.md).
- **After changing notebooks, reference CSVs or `transform/`,** run `databricks bundle deploy`. Airflow reads `ingestion/` and `transform/` live from the mounted folders; Databricks uses the deployed copy.
- **Power BI files:** close Desktop before editing the TMDL or PBIR files by hand, because Desktop rewrites them when it saves.
