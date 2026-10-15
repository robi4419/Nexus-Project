# Nexus-Project: Plan

Pull remote job postings from the [Jobicy API](https://jobi.cy/apidocs), extract the skills and technologies each posting asks for, and build dashboards you can filter by country, industry, seniority and date.

**Stack:** Apache Airflow (orchestration), Databricks (storage, cleaning, normalisation, dedup, skill extraction), dbt (analytical models), Databricks AI/BI dashboards, Docker (runs Airflow), GitHub and GitHub Actions (version control and CI), DrawDB (data-model diagram).

## Jobicy data

Useful fields: `id`, `url`, `jobTitle`, `companyName`, `jobIndustry[]`, `jobType[]`, `jobGeo`, `jobLevel`, `jobDescription` (HTML), `pubDate`, `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryPeriod`. Paging uses `nextCursor` and `hasMore`.

Things to handle:
- `jobGeo` is free text ("USA", "Anywhere", "EMEA", "USA, Canada"). Normalise it to country/region before using it as a filter.
- Many postings are non-tech (Sales, Marketing). The skills taxonomy should cover business tools too (Salesforce, HubSpot, Excel).
- Jobicy asks for credit and a link back to the original job `url`. Show `url` on dashboards and keep polling to a few times a day.

## Flow

```
 Jobicy API (job postings)              Frankfurter API (daily ECB exchange rates)
     │  (1) ingest_jobicy, daily             │  (1b) ingest_fx_rates, weekdays (backfills)
     ▼                                       ▼
 Unity Catalog Volume  /Volumes/<catalog>/bronze/landing/<source>/ingest_date=YYYY-MM-DD/run=<run id>/*.json
     │  (2) Databricks Job "transform_jobs": Auto Loader loads each new file once
     ▼
 BRONZE  jobicy_raw · frankfurter_raw   (append-only, one row per landed file, JSON kept as VARIANT)
     │  (3) same Job: rebuild silver (clean, normalise, dedup, skills, salaries in USD), then checks
     ▼
 SILVER  jobs · job_locations · job_industries · job_types · job_skills · fx_rates · ref_skills · ref_locations
     │  (4) Airflow runs dbt build: staging → intermediate → marts, plus tests
     ▼
 GOLD (dbt)  dim_skill · dim_geo · dim_industry · dim_company · dim_date
             fct_job_postings · fct_job_skill
             agg_skill_demand_by_country_month · skill_co_occurrence · salary_by_skill
     │  (5)
     ▼
 Databricks AI/BI dashboards (filters: country, industry, level, job type, date)
```

Design principles:
1. **Keep the raw data untouched.** Skill extraction will be improved many times; the original API responses let you reprocess all history without calling the API again.
2. **Fetch the whole feed window each run.** The feed only covers the last 7 days (~800 jobs, 4 pages of 200), so every run takes all of it. Silver is rebuilt from bronze on every run and keeps the latest version of each job, which removes the duplicates.
3. **Do skill extraction in Databricks (PySpark).** Keep a version-controlled taxonomy (`skill, category, aliases/regex`, e.g. `k8s|kubernetes → Kubernetes`). Strip HTML, match with word boundaries, and treat ambiguous names ("Go", "R", "C", "C#", ".NET", "Node.js", "Excel") with case-sensitive patterns or context rules.
4. **Use dbt for business logic only.** It reads Silver as sources, builds a star schema and aggregates, and runs tests.
5. **Build dashboards in Databricks AI/BI** and export them as `.lvdash.json` into `dashboards/` so they're versioned.
6. **Airflow runs the chain** on a schedule (daily; Jobicy asks for no more than one sync per hour).

Dashboard ideas: top skills by country, industry and seniority; skill demand over time and rising skills (week-over-week); skill co-occurrence heatmap; median salary by skill; remote-geo coverage map; share of postings listing salary; top hiring companies per skill.

## Development plan

Each phase gets a detailed plan in [`docs/phases/`](phases/) when work on it starts:
- [Phase 0: Fix the scaffolding](phases/phase-0-scaffolding.md)
- [Phase 1: Ingestion](phases/phase-1-ingestion.md)
- [Phase 2: Bronze and Silver in Databricks](phases/phase-2-bronze-silver.md)

### Phase 0: Fix the scaffolding
- [x] `airflow/Dockerfile` extending `apache/airflow:3.3.2` with `apache-airflow-providers-databricks`; install dbt in a separate virtualenv inside the image (dbt and Airflow pin conflicting dependencies).
- [x] Move `docker-compose.yaml` to the repo root, build the custom image, mount `dbt/` and `ingestion/`, use one root `.env` for Databricks and Airflow settings.
- [x] Replace the `example:` block in `dbt/job_listings/dbt_project.yml` with `staging/intermediate/marts` configs.
- [x] Move `test.py` into `ingestion/`; split requirements into local dev, Airflow and dbt.
- [x] Verify the stack builds, starts, and reaches Databricks from the worker.

### Phase 1: Ingestion
- [x] Multi-source layout: shared `ingestion/common/` (HTTP session, Volume writer) and `ingestion/sources/jobicy/` (cursor paging over the full 7-day window).
- [x] Write raw JSON to a UC Volume with `databricks-sdk`: `landing/<source>/`, one file per page, one folder per run.
- [x] Airflow DAG `ingest_jobicy`: `ensure_landing_volume` → `fetch_and_land` → `check_run`, daily at 18:00 UTC; updates the Asset `landing/jobicy`.
- [x] Unit tests against a saved sample response.
- [x] Put it on a schedule early so history starts accumulating.
- [ ] Optional: add more sources (Arbeitnow, Himalayas) using the same layout.

### Phase 2: Bronze and Silver in Databricks
- [ ] Exchange-rate source (Frankfurter/ECB): client, landing, tests, `ingest_fx_rates` DAG with backfill.
- [ ] Databricks Asset Bundle (`databricks.yml`) defining the `transform_jobs` Job, deployed with the Databricks CLI.
- [ ] Bronze: Auto Loader into `bronze.jobicy_raw` and `bronze.frankfurter_raw` (one row per landed file, VARIANT).
- [ ] Reference data (`skills.csv` with ~250 skills, `locations.csv`) and a tested `transform/` package (HTML to text, seniority, skill matcher).
- [ ] Silver rebuilt each run: `jobs`, `job_locations`, `job_industries`, `job_types`, `job_skills`, `fx_rates`; salaries in yearly USD.
- [ ] Data-quality checks; hand-check 50 postings (skill precision ≥ 90%).

### Phase 3: dbt models
- [ ] `sources.yml` on silver; `stg_*` → `int_*` → marts (`dim_*`, `fct_*`, aggregates).
- [ ] Tests (unique, not_null, relationships, accepted_values) and `dbt docs generate`; `dbt_utils` where useful.
- [ ] ER diagram in DrawDB, saved to `docs/`.

### Phase 4: Orchestration end to end
- [ ] Full DAG: extract → upload → Databricks job → `dbt build` (BashOperator with the dbt venv, or astronomer-cosmos for per-model tasks).
- [ ] Retries, failure alerts, backfill support.

### Phase 5: Dashboards
- [ ] 2–3 AI/BI dashboards on gold tables with global filters (country, industry, level, job type, date range).
- [ ] Export to `dashboards/` and include in the bundle.

### Phase 6: GitHub and CI (can start alongside Phase 1)
- [ ] Feature branches and PRs.
- [ ] Actions on PR: `ruff`, `pytest`, Airflow DAG import test, `dbt parse`, `sqlfluff`.
- [ ] Optional: `databricks bundle deploy` on merge to `main`.
- [ ] README with architecture diagram and setup steps.

### Phase 7: Polish (optional)
- [ ] LLM-based skill extraction (`ai_query`) compared with the dictionary approach.
- [ ] Data-quality checks (alert if a run returns 0 jobs).
- [ ] Skill category groupings.
