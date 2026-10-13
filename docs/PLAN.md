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
 Jobicy API
     │  (1) Airflow task: pull new postings (cursor paging), save the raw JSON untouched
     ▼
 Databricks Unity Catalog Volume  /landing/jobicy/dt=YYYY-MM-DD/*.json
     │  (2) Databricks job: bronze (raw Delta table, append-only, with ingest timestamp)
     ▼
 BRONZE  jobicy_raw
     │  (3) Databricks job (PySpark): clean, normalise, dedup, extract skills
     ▼
 SILVER  jobs (one row per job id, MERGE on id) · job_skills (job_id, skill) · job_industries ...
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
2. **Load incrementally.** Store the newest `pubDate`/`id` seen, page with `nextCursor` until a known posting appears, then stop. The Silver `MERGE` on `id` removes duplicates.
3. **Do skill extraction in Databricks (PySpark).** Keep a version-controlled taxonomy (`skill, category, aliases/regex`, e.g. `k8s|kubernetes → Kubernetes`). Strip HTML, match with word boundaries, and treat ambiguous names ("Go", "R", "C", "C#", ".NET", "Node.js", "Excel") with case-sensitive patterns or context rules.
4. **Use dbt for business logic only.** It reads Silver as sources, builds a star schema and aggregates, and runs tests.
5. **Build dashboards in Databricks AI/BI** and export them as `.lvdash.json` into `dashboards/` so they're versioned.
6. **Airflow runs the chain** on a schedule (e.g. every 6 hours).

Dashboard ideas: top skills by country, industry and seniority; skill demand over time and rising skills (week-over-week); skill co-occurrence heatmap; median salary by skill; remote-geo coverage map; share of postings listing salary; top hiring companies per skill.

## Development plan

Each phase gets a detailed plan in [`docs/phases/`](phases/) when work on it starts:
- [Phase 0: Fix the scaffolding](phases/phase-0-scaffolding.md)

### Phase 0: Fix the scaffolding
- [ ] `airflow/Dockerfile` extending `apache/airflow:3.3.2` with `apache-airflow-providers-databricks`; install dbt in a separate virtualenv inside the image (dbt and Airflow pin conflicting dependencies). Switch compose to `build: .`.
- [ ] Mount `../dbt` and the ingestion package into the containers; pass `DATABRICKS_*` variables or create an Airflow `databricks_default` connection.
- [ ] Replace the `example:` block in `dbt/job_listings/dbt_project.yml` with `staging/intermediate/marts` configs.
- [ ] Move `test.py` into `ingestion/`; split requirements into dev and Airflow.

### Phase 1: Ingestion
- [ ] `ingestion/jobicy_client.py`: requests with retries/backoff, cursor paging, stop at the watermark.
- [ ] Write raw JSON to a UC Volume with `databricks-sdk`, one file per run per date.
- [ ] Airflow DAG `jobicy_pipeline`: `extract` → `upload`; store the watermark in an Airflow Variable or a small Delta table.
- [ ] Unit tests against a saved sample response.
- [ ] Put it on a schedule early so history starts accumulating.

### Phase 2: Bronze and Silver in Databricks
- [ ] Catalog and schemas: `bronze`, `silver`, `gold`.
- [ ] `01_bronze`: Auto Loader or `COPY INTO` from the Volume into `bronze.jobicy_raw`.
- [ ] `02_silver`: strip HTML, flatten arrays into bridge tables, map `jobGeo` to country/region, convert salaries to yearly USD, `MERGE` on `id`.
- [ ] `skills_taxonomy.csv` (~200 skills by category) and `03_skill_extraction` → `silver.job_skills`. Hand-check ~50 postings for accuracy.
- [ ] Package jobs with Databricks Asset Bundles (`databricks.yml`).

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
