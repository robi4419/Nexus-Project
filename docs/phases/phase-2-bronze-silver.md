# Phase 2: Bronze and Silver in Databricks

**Why:** Phase 1 lands the full Jobicy feed every evening as raw JSON files. Nothing can use that data yet: it's nested JSON with HTML descriptions, free-text locations, salaries in 12 currencies, unreliable seniority labels, and the same job repeated across daily runs. Phase 2 turns it into clean, deduplicated **silver** tables, including the skills each posting asks for, so dbt (Phase 3) and the dashboards (Phase 5) can rely on them.

**Goal:** a Databricks Job, deployed from the repo, that turns landed raw files into **bronze** tables (raw, append-only) and **silver** tables. Silver means clean, one row per job, with:
- locations mapped to countries and regions
- seniority taken from job titles
- salaries converted to yearly USD using daily exchange rates
- extracted skills

The Job also runs data-quality checks. A second ingestion source, daily ECB exchange rates from the Frankfurter API, is added following the Phase 1 "Adding another API" checklist.

**Done when:**
- `pytest` passes, including new tests for text cleaning, seniority, skill matching, the reference data and the exchange-rate client.
- The `ingest_fx_rates` DAG runs on weekdays and has filled in rates since 2026-10-01.
- `databricks bundle deploy` creates the `transform_jobs` Job, and `databricks bundle run transform_jobs` finishes green, including the checks task.
- Silver row counts match bronze: no job lost, no job duplicated, and every location and salary currency is mapped.
- Running the Job again with no new files changes nothing.
- A hand-check of 50 postings is recorded, with skill-match precision of at least 90%.

## Progress
- [x] 2.1 Branch, docs and Databricks CLI (v1.21.0, `DEFAULT` profile with personal access token)
- [x] 2.2 Exchange-rate source (Frankfurter): client, landing, tests, `ingest_fx_rates` DAG (10 tests; unpaused 2026-10-15, backfilled 10 weekdays 2026-10-01 → 10-14, each folder holds that day's ECB rates, 29 currencies)
- [x] 2.3 Asset Bundle skeleton (`databricks.yml`, Job definition): validated and deployed 2026-10-15 as `[dev robix4000] transform_jobs`
- [x] 2.4 Bronze: Auto Loader into `bronze.jobicy_raw` and `bronze.frankfurter_raw` (2026-10-15: first run loaded 4 Jobicy files / 751 jobs and 11 rate files; an immediate re-run loaded 0; after the 18:00 Jobicy ingestion, a re-run loaded exactly its 4 new files and 0 rate files)
- [x] 2.5 Reference data: `skills.csv`, `locations.csv`, and their tables
- [ ] 2.6 `transform/` package: HTML to text, seniority, skill matcher, with unit tests
- [ ] 2.7 Silver exchange rates: `silver.fx_rates`
- [ ] 2.8 Silver jobs: `silver.jobs`, plus location, industry and type bridge tables
- [ ] 2.9 Silver skills: `silver.job_skills`
- [ ] 2.10 Data-quality checks
- [ ] 2.11 Verify end to end, idempotency, and hand-check of 50 postings
- [ ] 2.12 Commit, PR and merge

---

## What the data looks like (profiled 2026-10-15)

| Area | Finding | Consequence |
|---|---|---|
| Compute | Serverless Starter Warehouse (2X-Small), **no clusters**. It's a serverless-only workspace (Free Edition-style). | Everything runs on serverless Jobs, and Auto Loader uses `trigger(availableNow=True)`. Keep the Job light, because of daily compute limits. |
| Raw reading | `read_files(... singleVariantColumn ...)`, `_metadata.file_path`, `explode(cast(x AS ARRAY<VARIANT>))` and `cast(obj AS MAP<STRING,DOUBLE>)` all work on Databricks SQL 2026.39. | Bronze stores each file's JSON as **VARIANT**, so API field changes can't break loading. |
| Volume | 4 files, 751 jobs, 244 companies (one run so far). | Each daily run adds ~4 files; most jobs repeat across runs. |
| Salaries | ~410 jobs list a salary: 80% USD, **12 currencies**; periods are yearly, hourly, monthly or missing. **Bad values exist**: an "hourly" 47,840 and a "monthly" 50. | Convert to yearly USD, and flag implausible values instead of trusting them. |
| `jobGeo` | 106 combinations of **55 official values** (50 countries/territories, plus Anywhere, APAC, EMEA, Europe, LATAM), separated by `",  "`. | Split, trim, and map each part through `locations.csv`. |
| `jobLevel` | Senior 290, **Director 277**, Any 137, Midweight 34, Entry-Level/Junior 13. Only **22%** of "Director" titles contain Director/Head/VP/Chief, and **57** are Account Executives. | Derive seniority from the title, and treat Jobicy's "Director" as unreliable. |
| Types / industries | 4 types, and 22 industries matching Jobicy's official list exactly. | Use them as they are. |
| Descriptions | HTML, average 7.5k characters, maximum 22.8k; 462 contain `&amp;`-style codes. | Clean HTML to text before matching skills. |
| Skill mentions | Python 125, **Salesforce 128**, SQL 94, AWS 88, Excel 36, HubSpot 30, Jira 20, Zendesk 16. These 8 alone appear in 48% of jobs. | Business tools matter as much as tech. |
| Frankfurter API | No key, all 12 salary currencies covered. Weekends and holidays return the previous working day's rates (Saturday 10-10 returned 10-09). Historical dates work. | The exchange-rate DAG can **backfill** past dates (`catchup=True`), unlike Jobicy. |

## Decisions (2026-10-15)

1. **Notebooks in a serverless Databricks Job**, not a Lakeflow pipeline. Steps are explicit and can be run cell by cell, Databricks does the cleaning and dbt does the modelling.
2. **Databricks Asset Bundles**: the Job is defined in YAML in the repo and deployed with the Databricks CLI, installed once with `winget`.
3. **Skills cover tech, business tools and certifications**: 351 entries in 18 categories (more than the ~250 first estimated, to cover the business tools non-tech postings ask for). Soft skills are left out.
4. **Locations are stored as listed, with regions.** A "Europe" job counts under region Europe, not under each European country. No expansion into countries.
5. **Daily ECB exchange rates come from the Frankfurter API**, as a second ingestion source with its own DAG. Salaries use the rate on or before the job's publish date (an *as-of join*).
6. **Silver is rebuilt from bronze on every run.** Bronze loads only new files (Auto Loader). This replaces the original plan's "MERGE on id".
7. **Seniority comes from the job title first, then falls back to Jobicy's level.** Refinement based on the data: in the fallback, Jobicy's **"Director" and "Any" become "Unspecified"**, while Senior, Midweight and Entry-Level/Junior are kept. Jobicy's raw value is always stored too.

### Other changes from the original plan
- Bronze has **one row per landed file** (the whole page as VARIANT) instead of one row per job. The `jobs` array is exploded in silver. This keeps the bronze notebook identical for every source.
- Pure-Python logic (HTML cleaning, seniority rules, skill matching) lives in a new top-level `transform/` package. It's unit-tested locally like `ingestion/`, then used inside Spark as Python functions (UDFs).

---

## How data flows in Phase 2

```
Airflow (Phase 1 + new)                          Databricks Job "transform_jobs" (serverless)

ingest_jobicy   18:00 daily ─► landing/jobicy/      ─► bronze_jobicy ──────────────┐
ingest_fx_rates 17:00 Mon–Fri ► landing/frankfurter/ ─► bronze_fx ─► silver_fx ─────┼─► silver_jobs ─► silver_skills ─► checks
repo databricks/reference/*.csv ─────────────────────► reference ──────────────────┘
```

For now the Job is run with `databricks bundle run`. Phase 4 makes Airflow trigger it automatically when the Assets update.

## Tables

**Bronze:** `bronze.jobicy_raw` and `bronze.frankfurter_raw` have the same columns. They're append-only, with one row per landed file.

| Column | Type | Meaning |
|---|---|---|
| `source` | STRING | `jobicy` / `frankfurter` |
| `file_path` | STRING | Volume path of the landed file |
| `ingest_date` | DATE | from the `ingest_date=` folder |
| `run_id` | STRING | from the `run=` folder |
| `landed_at` | TIMESTAMP | file modification time, i.e. when Airflow wrote it |
| `loaded_at` | TIMESTAMP | when the row entered bronze |
| `body` | VARIANT | the whole JSON file, untouched |

**Silver:** rebuilt on every run with `CREATE OR REPLACE TABLE`. That's atomic, so readers never see half a table, and Delta keeps the previous versions.

| Table | One row per | Main columns |
|---|---|---|
| `silver.jobs` | job (`source`, `source_job_id`) | `url`, `title`, `company_name`, `company_logo_url`, `published_at`, `published_date`, `seniority`, `seniority_source`, `source_level`, `geo_raw`, `excerpt`, `description_text`, `salary_min/max/currency/period` (as given), `salary_min_usd_yearly`, `salary_max_usd_yearly`, `salary_is_plausible`, `fx_rate_date`, `first_seen_at`, `last_seen_at`, `times_seen`, `is_listed_now`, `built_at` |
| `silver.job_locations` | job × location | `location_raw`, `location_name`, `location_type` (country / region / worldwide / unknown), `country_code`, `region` |
| `silver.job_industries` | job × industry | `industry` |
| `silver.job_types` | job × type | `job_type` |
| `silver.job_skills` | job × skill | `skill`, `category`, `mentions`, `in_title`, `taxonomy_version` |
| `silver.fx_rates` | date × currency | `rate_date`, `currency`, `units_per_usd`, `usd_per_unit` (USD = 1 included) |
| `silver.ref_skills`, `silver.ref_locations` | reference row | loaded from the CSVs, so dbt can build `dim_skill` and `dim_geo` |

Regions: North America, LATAM, Europe, Middle East & Africa, APAC, EMEA, Worldwide. EMEA stays its own value, so filtering by Europe doesn't include EMEA-wide jobs.

Seniority values: Intern, Junior, Mid, Senior, Lead, Director, Executive, Unspecified.

## Repo layout additions

```
databricks.yml                         ← bundle root: name, variables (catalog), sync rules, target "dev"
databricks/
    resources/transform_jobs.job.yml   ← the Job: tasks, order, parameters (no schedule; Airflow triggers it in Phase 4)
    notebooks/                          ← Databricks "source format" .py notebooks (plain text, diff-friendly)
        01_bronze.py                   ← Auto Loader, parameter `source` (used by 2 tasks)
        02_reference.py                ← CSVs → silver.ref_*
        03_silver_fx.py
        04_silver_jobs.py
        05_silver_skills.py
        06_checks.py
        review_skills.py               ← not in the Job: hand-check sample + "missing skill" candidates
    reference/
        skills.csv                     ← skill, category, aliases (| separated), case_sensitive
        locations.csv                  ← raw_value, location_name, location_type, country_code, region
transform/                              ← pure Python (stdlib only), imported by notebooks, tested locally
    text.py                            ← html_to_text()
    seniority.py                       ← seniority rules + fallback
    skills.py                          ← taxonomy loading, SkillMatcher, taxonomy_version()
ingestion/sources/frankfurter/
    client.py, land.py                 ← same shape as ingestion/sources/jobicy/
airflow/dags/ingest_fx_rates.py
tests/  (flat, as now)
    test_text.py, test_seniority.py, test_skills.py, test_reference_data.py,
    test_frankfurter_client.py, test_frankfurter_land.py, fixtures/frankfurter_rates.json
```

**What's reused:**
- `build_session()` from `ingestion/common/http.py`
- `LandingVolume`, `ensure_volume`, `run_folder`, `reset_folder` and `write_file` from `ingestion/common/landing.py`
- `FakeResponse`, `FakeSession` and `FakeWorkspaceClient` from `tests/fakes.py`
- the DAG shape of `airflow/dags/ingest_jobicy.py`
- the pytest config in `pyproject.toml`

---

## Tasks

### 2.1 Branch, docs and Databricks CLI
- Branch `phase-2-bronze-silver`; save this doc; update `PLAN.md`.
- **You run:** `winget install Databricks.DatabricksCLI`, then open a new terminal so PATH updates, then `databricks -v`.
- **You run:** `databricks configure`, and enter the host and token from `.env`. That saves a profile to `C:\Users\Robert\.databrickscfg`, outside the repo. Check it with `databricks current-user me`.

### 2.2 Exchange-rate source (Frankfurter)
Follow the Phase 1 checklist "Adding another API later":
- `ingestion/sources/frankfurter/client.py`: `fetch_rates(session, on_date, base="USD")` calls `https://api.frankfurter.dev/v1/<date>?base=USD`. It checks `base` and that `rates` isn't empty, raising `FrankfurterAPIError` otherwise, and returns the raw bytes plus the parsed `date` and `rates`.
- `ingestion/sources/frankfurter/land.py`: writes `landing/frankfurter/ingest_date=…/run=…/rates.json` using `ingestion.common.landing`, and returns a small summary (requested date, `rate_date`, currency count, folder).
- Tests with a saved response and the existing fakes.
- `airflow/dags/ingest_fx_rates.py`: `ensure_landing_volume` → `fetch_and_land` → `check_run` (fails if there are fewer than 20 currencies or EUR is missing). Settings:
  - `CronTriggerTimetable("0 17 * * 1-5", timezone="UTC")`: weekdays, after the ECB publishes around 16:00 CET.
  - **`catchup=True`** with `start_date=2026-10-01`. Each run asks for **its own date**, so unpausing backfills about 11 weekdays, and days missed while the PC was off are filled in automatically.
  - Asset `landing/frankfurter`, `max_active_runs=1`, retries as in Jobicy.

### 2.3 Asset Bundle skeleton
- `databricks.yml` at the repo root:
  - bundle `nexus`;
  - `include: databricks/resources/*.yml`;
  - variable `catalog` (default `workspace`);
  - `sync` excludes `airflow/`, `dbt/`, `docs/`, `tests/`, `ingestion/` and `dashboards/`. `.env` and `.venv` are already excluded through `.gitignore`;
  - target `dev`, `mode: development`, set as the default.
- `databricks/resources/transform_jobs.job.yml`:
  - Job `transform_jobs`, with `max_concurrent_runs: 1`;
  - Job parameters `catalog` and `bundle_root: ${workspace.file_path}`;
  - the task graph shown above;
  - serverless (no cluster definition).
- Check: `databricks bundle validate`, then `deploy`, then the Job appears under **Jobs & Pipelines**, named `[dev <you>] transform_jobs`.

### 2.4 Bronze
`01_bronze.py`, with parameters `catalog` and `source`:
- `CREATE VOLUME IF NOT EXISTS bronze.checkpoints`.
- Auto Loader (`cloudFiles`) reads `landing/<source>/` with:
  - `cloudFiles.format=json`, `multiLine=true`;
  - `singleVariantColumn=body`;
  - `cloudFiles.allowOverwrites=true`, so a file re-landed by an Airflow Clear is loaded again as a new row.
- It adds the columns from the table above. `ingest_date` and `run_id` are parsed from `_metadata.file_path`.
- It writes to `bronze.<source>_raw` with `trigger(availableNow=True)`. The checkpoint is `/Volumes/<catalog>/bronze/checkpoints/<source>_raw`.
- Two Job tasks use this notebook: `bronze_jobicy` and `bronze_fx`.

### 2.5 Reference data
- `skills.csv`: 351 skills in 18 categories:
  - Programming Languages, Web & Mobile Frameworks, Data Engineering, Data Science & AI, Analytics & BI, Databases, Cloud, DevOps & Infrastructure, Security, Testing & QA
  - CRM & Sales Tools, Marketing & SEO Tools, Customer Support Tools, Finance & ERP, Productivity & Project Management, Design Tools, HR & Recruiting Tools, Certifications

  Aliases are plain phrases, not regexes, and only the listed aliases are searched (the skill name isn't added automatically). An alias starting with `-` is an **exclusion**: a match inside that phrase doesn't count (React has `-React Native`, Looker has `-Looker Studio`, Excel has `-Excel at` and `-Excel in`, Greenhouse has `-Greenhouse Gas`). Ambiguous names only match through safe aliases or case-sensitively:
  - Go → `Golang`, `Go developer`...
  - R → `R programming`, `RStudio`...
  - C → `C/C++`, `Embedded C`
  - case-sensitive `Excel`, `Slack`, `Notion`, `Spark`
  - `dbt` (so "DBT therapy" in healthcare jobs doesn't count)
- `locations.csv`: all 55 Jobicy values, plus extra spellings for future sources ("United States", "Remote"...). `Türkiye` needs UTF-8.
- `02_reference.py` reads the CSVs from the bundle folder (with pandas, on the driver) and writes `silver.ref_skills` and `silver.ref_locations`. It creates `silver` if it's missing.
- `tests/test_reference_data.py` checks:
  - columns and allowed categories, location types and regions;
  - no alias belongs to two skills;
  - no duplicate `raw_value`;
  - every Jobicy location value is present.

### 2.6 `transform/` package (unit-tested locally)
- `text.py`: `html_to_text(html)` turns block tags into line breaks, removes the other tags, converts `html.unescape` codes like `&amp;`, and collapses whitespace.
- `seniority.py`: `seniority(title, source_level) -> (seniority, seniority_source)`. Rules are case-insensitive, and the first match wins:
  - Executive (Chief, CEO/CTO/CFO/COO/CMO/CRO/CISO/CIO, VP, Vice President)
  - Director (Director, Head of)
  - Lead (Lead, Principal, Staff)
  - Senior (Senior, Sr)
  - Mid (Mid-level, Intermediate)
  - Junior (Junior, Jr, Entry level, Graduate, Associate)
  - Intern (Intern, Internship, Trainee, Apprentice)

  Tests cover the known traps: "Account **Executive**", "**Lead** Generation", "**Staff** Accountant", "Product **Manager**".

  The fallback: Senior → Senior, Midweight → Mid, Entry-Level/Junior → Junior, Director/Any → Unspecified.
- `skills.py`: `SkillMatcher` loads `skills.csv`.
  - Each alias is matched as a whole word. Boundaries treat `+ # .` as part of a word, so C++, C#, .NET and Node.js work, and Java doesn't match inside JavaScript.
  - Matching is case-insensitive unless the skill is flagged `case_sensitive`.
  - **Different skills may overlap**: "C/C++" counts for C and C++, "Spark SQL" for Spark and SQL. (The plan first said "the longest match wins", but that would make "C/C++" lose C++.) Overlaps that are wrong are prevented with the skill's exclusion phrases, e.g. React's `-React Native`.
  - `match(title, text)` returns skill, category, mentions and in_title.
  - `taxonomy_version()` is a short hash of the CSV, stored with every result so you can tell which skill list produced it.

### 2.7 Silver exchange rates
`03_silver_fx.py` turns `bronze.frankfurter_raw` into `silver.fx_rates`:
- `explode(cast(body:rates AS MAP<STRING,DOUBLE>))`, plus a USD = 1 row for each date;
- keep the latest file per (`rate_date`, `currency`).

### 2.8 Silver jobs
`04_silver_jobs.py`:
1. **Observations:** explode `body:jobs` from `bronze.jobicy_raw`, giving one row per job per run. Each future source gets its own "conform" view with the same columns, and all are combined with `UNION ALL`.
2. **History per job:** `first_seen_at`, `last_seen_at`, `times_seen` (distinct runs), and `is_listed_now` (present in the source's latest run).
3. **Latest version per job:** `QUALIFY row_number() OVER (PARTITION BY source, source_job_id ORDER BY landed_at DESC) = 1`.
4. **Cleaning:** UDFs for `html_to_text` and `seniority`; `to_timestamp(pubDate)`.
5. **Salary:**
   - yearly factor: yearly 1, monthly 12, weekly 52, daily 260, hourly 2080;
   - **as-of join** to `silver.fx_rates`: the latest `rate_date` on or before `published_date`;
   - `salary_is_plausible` means yearly USD is between 5k and 1.5M, and min ≤ max.
6. **Bridge tables:**
   - `job_industries` and `job_types` (explode the arrays);
   - `job_locations` (`split(geo_raw, ',')`, trim and collapse spaces, then join `ref_locations` case-insensitively; unmatched values become `unknown`).

### 2.9 Silver skills
`05_silver_skills.py`:
- loads `SkillMatcher` from the bundle's `skills.csv`;
- a Python UDF runs over `title` and `description_text` from `silver.jobs`;
- explode the results, then `CREATE OR REPLACE TABLE silver.job_skills`;
- print `taxonomy_version` and the top 20 skills.

### 2.10 Data-quality checks
`06_checks.py` prints a results table and **fails the task on any error**. The data is still written; the red run is the alert.

- **Errors:**
  - `(source, source_job_id)` is unique;
  - title, url, published_at and company_name are not null;
  - silver job count equals the number of distinct jobs in bronze;
  - every job has at least 1 location, and no location is `unknown`;
  - every salary currency has an exchange rate;
  - every skill in `job_skills` exists in `ref_skills`.
- **Warnings:**
  - share of jobs with at least 1 skill: overall, and for Software Engineering (target ≥ 90%);
  - more than 5% of salaries implausible;
  - newest `landed_at` is more than 2 days old (ingestion may have stopped);
  - share of seniority = Unspecified.

### 2.11 Verify
1. `pytest` passes, both the old 25 tests and the new ones.
2. Unpause `ingest_fx_rates`: the backfill runs go green, and there's one `rates.json` per run in `landing/frankfurter/`.
3. `databricks bundle validate` and `databricks bundle deploy` succeed.
4. `databricks bundle run transform_jobs`: all 7 tasks are green and the checks pass.
5. Spot-check in the SQL editor:
   - row counts per table;
   - 10 jobs with seniority, locations and USD salary;
   - top skills by industry.
6. **Idempotency:** run the Job again. Bronze row counts don't change (nothing new), and silver counts are identical.
7. After the next daily Jobicy run: bronze gains about 4 rows, `silver.jobs` grows only by new jobs, and `times_seen` goes up for jobs seen again.
8. **Hand-check:** `review_skills.py` samples 50 jobs across industries. Together we mark wrong and missing skills, and record precision (correct ÷ found, target ≥ 90%) and missed skills in this doc. Improve `skills.csv`, using the notebook's "candidate terms" list too, then re-run.

### 2.12 Commit, PR and merge
Small commits per step (FX source, bundle, bronze, reference data, transform package, silver, skills, checks, docs), then push, PR, merge, and update local `main`.

---

## Concepts you'll meet
- **Medallion layers:** bronze is raw as received, silver is cleaned and conformed, gold is business-ready (dbt).
- **Delta table:** Databricks' table format. It supports atomic writes and keeps a version history (`DESCRIBE HISTORY`, time travel).
- **VARIANT:** a column type that stores any JSON as-is. Read fields with `body:field::type`.
- **Auto Loader (`cloudFiles`):** finds new files in a folder and loads each one exactly once. It remembers what it loaded in a **checkpoint**.
- **`trigger(availableNow=True)`:** process every new file, then stop. Batch-style streaming, the only kind serverless supports.
- **`CREATE OR REPLACE TABLE … AS SELECT`:** rebuild a table atomically.
- **Window functions and `QUALIFY`:** rank rows within groups, then keep rank 1. That's how the latest version of each job is picked.
- **`explode` and bridge tables:** turn one row with a list into one row per item. That's how job × location and job × skill tables are built.
- **As-of join:** join each row to the latest record on or before its date. That's how each salary gets the right exchange rate.
- **UDF (user-defined function):** a Python function used inside Spark SQL.
- **Databricks Job, tasks and parameters:** a Job is a graph of tasks with dependencies; parameters arrive in notebooks as widgets (`dbutils.widgets.get`).
- **Notebook source format:** a `.py` file starting with `# Databricks notebook source`, with cells separated by `# COMMAND ----------`.
- **Asset Bundles:** `databricks.yml` plus resource YAML files describe Jobs as code. `validate`, `deploy` and `run` are CLI commands. A **target** is where it deploys to. **Development mode** prefixes names with `[dev you]`.
- **CLI profile:** saved host and token in `~/.databrickscfg`, which the CLI uses to log in.
- **Airflow catchup and backfill:** creating runs for past dates, which works here because the exchange-rate API serves history.
- **Precision and recall:** of the skills found, how many are right; of the skills present, how many were found.

## Pitfalls
- **Backslashes in SQL strings:** in our test, `'\\b'` became a backspace character. Write SQL regexes as raw strings, `r'\b...'`, and keep complex matching in tested Python.
- **Checkpoint and bronze table belong together:** deleting only the checkpoint reloads every file and duplicates bronze. To reset, drop both.
- **Re-landed files** (after an Airflow Clear) are loaded again as new bronze rows. That's harmless, because silver keeps the latest version per job.
- **Workspace files** (our CSVs and `transform/`) are read on the driver through normal file paths, not through `spark.read`.
- **Serverless only:** no `%pip` packages are needed (`transform/` uses only the standard library). Python UDFs are slower than SQL, so they're used only for text cleaning and matching.
- **Development-mode name:** the Job is called `[dev <you>] transform_jobs`. Phase 4 will look up its ID.
- **CLI on Windows:** open a new terminal after installing. The token in `.databrickscfg` stays out of the repo.
- **Ambiguous skills and titles:** Go, R, C, Excel, Slack, Spark, dbt/DBT, Swift, Lead Generation, Staff Accountant, Account Executive. Each needs a unit test.
- **Exchange-rate dates:** weekends and holidays return the previous working day, so `rate_date` can differ from the requested date.
- **Free Edition limits:** keep the Job small. The warehouse and serverless compute stop on their own when idle.
