# Phase 3: dbt models

**Goal:** a dbt project that turns silver into **gold**: a star schema (dimensions, facts and bridge tables) plus a few aggregates, ready for the Phase 5 dashboards. Every model is tested, documented and, on the marts, protected by a contract. The models are written by the user, step by step, with Claude explaining and reviewing (decision 1).

**Done when:**
- `dbt build` passes locally against `workspace.gold`. It runs every model, seed and test in dependency order. The only warning allowed is the salary-plausibility share.
- The marts have enforced contracts: column types, `NOT NULL`, and primary and foreign keys.
- Row counts reconcile with silver: one fact row per silver job, and one `fct_job_skills` row per silver job × skill.
- `dbt docs generate` works, and the descriptions also appear as comments in Unity Catalog.
- An ER diagram of the marts, made in DrawDB, is saved in `docs/`.
- `pytest` still passes.

## Progress
- [x] 3.1 Branch, plan doc, `PLAN.md`
- [x] 3.2 Project setup: `dbt_utils` package, sources on silver (tests, freshness), project config
- [x] 3.3 Staging models, one per silver table, with tests
- [x] 3.4 Intermediate models: job postings with the salary-plausibility flag, skill pairs
- [x] 3.5 Dimensions: date, skill, country, company, industry, seniority (seed)
- [x] 3.6 Facts and bridges with contracts: job postings, job skills, job locations, industries and types; `dim_location` replaces `dim_country` (decision 12)
- [ ] 3.7 Aggregates: skill demand by country and month, skill co-occurrence, salary by skill. Decide first how the dashboards' global filters reach them (decision 11)
- [ ] 3.8 Tests and the salary warning; `dbt build` green
- [ ] 3.9 Docs: descriptions, `dbt docs generate`, ER diagram in DrawDB
- [ ] 3.10 Verify, commit, PR and merge

---

## Starting point (2026-10-26)

| Area | State |
|---|---|
| dbt | dbt-core 1.12.5 with dbt-databricks 1.12.7, in the local `.venv` and in the Airflow image's own virtualenv (`/opt/dbt-venv`, for Phase 4) |
| Project | `dbt/job_listings`: `dbt_project.yml` makes staging and intermediate models views in `<schema>_staging`, and marts tables in `<schema>`. Only the starter example ever ran (Phase 0). |
| Connection | `profiles.yml` reads `DATABRICKS_HOST`, `DATABRICKS_WAREHOUSE_ID`, `DATABRICKS_TOKEN`, `DATABRICKS_CATALOG` (`workspace`) and `DATABRICKS_SCHEMA` (`gold`) from the environment. `dbt debug` passed on 2026-10-26. |
| Silver | `jobs` 15,202 · `job_skills` 71,762 · `job_locations` 17,548 · `job_industries` 12,642 · `job_types` 11,277 · `ref_skills` 384 · `ref_countries` 252 |

**Running dbt locally:** `profiles.yml` needs the `.env` values, which PowerShell doesn't load. `python-dotenv`'s `dotenv run` loads them into one command:

```
.venv\Scripts\dotenv.exe -f .env run -- .venv\Scripts\dbt.exe build --project-dir dbt/job_listings --profiles-dir dbt/job_listings
```

## Decisions (2026-10-26)

1. **The user writes the models; Claude explains each one in detail, reviews it and runs it.** Same way of working as the token-based skill matcher.
2. **dbt runs locally** from `.venv`, with `.env` loaded by `dotenv run`, and Claude runs the commands. Phase 4 runs the same project from the Airflow container.
3. **Gold is rebuilt from current silver.** Himalayas counts only its open jobs (about 60 days), so older months lose their Himalayas share as jobs expire. Trend charts in Phase 5 can label that or use Jobicy and Arbeitnow. Rejected: an incremental model freezing monthly counts. It's more complex, and frozen counts can't be filtered by every dimension.
4. **Attributes with several values per job become bridge tables:** locations, industries and job types. Skills are a fact table of their own, with mentions and the in-title flag. That's the standard star-schema answer to many-to-many; counts across a bridge use `count(distinct job_key)`.
5. **Single-column surrogate keys** (`job_key`, `company_key`) are built with `dbt_utils.generate_surrogate_key`. A composite key such as (`source`, `source_job_id`) is awkward in relationship tests and foreign keys.
6. **Gold leaves out the description text.** Dashboards need the title, company and `url`: Jobicy asks for a link back, and Himalayas requires its `applicationLink`. Skills are already extracted.
7. **Salary plausibility, from Phase 2:** a salary is plausible when its yearly USD values are between 5,000 and 1,500,000 and the minimum doesn't exceed the maximum. A test warns when more than 5% of salaried jobs are implausible, and salary charts use plausible salaries only.
8. **`company_key` ignores case and surrounding spaces:** it's the surrogate key of `lower(trim(company_name))`. That gives 5,194 companies instead of 5,243 exact names; decoding `&amp;` merges nothing more. The key leaves out the source, so the 187 companies posting on several sources get one key. `dim_company` shows the name from each company's latest posting.
9. **One-sided salaries use the bound they have.** 12 Jobicy jobs give only a minimum or only a maximum, so the missing bound is filled with the other one (`coalesce`) for both the midpoint and the plausibility check. Jobs without a yearly USD salary get a NULL `salary_is_plausible`, not false, so they stay out of the warning's denominator. As of 2026-10-26, 29 of 3,171 salaried jobs (0.9%) are implausible.
10. **`fct_job_skills` carries the job's dimension keys** (`published_date`, `company_key`, `seniority`) next to `job_key`, so skill charts join every dimension directly instead of going through `fct_job_postings` (a fact-to-fact join). It also copies the three job attributes skill charts filter by: `source` (trends without Himalayas, see decision 3), `is_listed_now` (current vs all-time demand) and `is_remote` (all on-site jobs are Arbeitnow's). Identifiers, lifecycle timestamps and salaries stay in `fct_job_postings`; salary by skill is `agg_salary_by_skill`. Job types get no dimension: their 5 names (Full-Time, Part-Time, Contract, Internship, Temporary) describe themselves, and an `accepted_values` test guards them. (2026-10-28)
11. **Gold stays a star schema with bridge tables** (reviewed 2026-10-28). The main questions are many-to-many (about 5 skills per job, several places, industries or types), and the star keeps one table per grain, so counts are correct by construction. AI/BI's global filters each get a plain column, and the dashboards' job lists need a job-grain table anyway. Rejected:
    - one big table with arrays: every chart has to `explode`, and AI/BI filters can't look inside a list;
    - one big exploded table: 183,965 rows for 23,590 jobs, so counts, averages and medians are wrong without de-duplicating;
    - a snowflake: extra joins, since region and category have no attributes of their own;
    - aggregates only: they can't be filtered by columns they weren't grouped by, and they have no job rows with links;
    - Data Vault: an unused layer, and keeping history would keep expired Himalayas jobs.

    **Open for 3.7:** a pre-grouped aggregate (month × place × skill) can't take the industry, level and job-type filters, and a median can't be re-filtered. Before writing 3.7, choose between dashboards querying the star directly (keeping `agg_*` only for heavy work like co-occurrence) and Unity Catalog metric views, which dbt-databricks 1.12.7 builds with `materialized='metric_view'`. Check first that the workspace supports metric views.
12. **`dim_location` replaces `dim_country`** (2026-10-28). It has one row per place: 1,384 on 2026-10-28, that is 1,024 cities, 249 countries, 5 regions, Worldwide and 105 unknown. Each place has exactly one region. Its columns are `location_key`, `location_name`, `location_type`, `country_code`, `country_name` and `region`; city, country and region roll up inside one flat dimension, so it stays a star.
    - `location_key` is the surrogate key of `location_type`, `location_name` and `country_code`. It's made once, in `stg_silver__job_locations`, like `job_key`.
    - `bridge_job_locations` holds only `job_key` and `location_key`, so no foreign key is NULL. With `dim_country`, 1,820 bridge rows (regions, Worldwide and unknown) had a NULL `country_code`, and an inner join silently dropped those jobs.
    - **Hierarchy-ready:** `region` → `country_name` → `city_name` are always filled, so BI tools can drill down without blank members. A missing level gets a label: `(whole country)`, `(anywhere)`, `(unknown)`, or for a regional place its own name in parentheses. Europe holds two regional places, `(Europe)` and `(Benelux)`, and a shared `(whole region)` label would have merged them. `country_code` stays NULL where there's no country, so map charts never get a fake ISO code, and `location_name` keeps the raw text of unknown places. Rolling up across the bridge needs a distinct count of `job_key`.

## How data flows in Phase 3

```
SILVER (Databricks Job)          dbt (local now, Airflow in Phase 4)
jobs, job_skills, job_locations ─► staging (views, gold_staging) ─► intermediate (views) ─► marts (tables, gold)
job_industries, job_types           stg_silver__*                      int_*                    dim_* · fct_* · bridge_* · agg_*
ref_skills, ref_countries                                                                          │
seed: seniority_levels.csv ────────────────────────────────────────────────────────────────────────┤
                                                                                                   ▼
                                                                                 Phase 5 dashboards
```

## Models

| Layer | Model | Grain (one row per) | From |
|---|---|---|---|
| staging | `stg_silver__jobs` | job | `silver.jobs`, plus `job_key` |
| staging | `stg_silver__job_skills`, `__job_locations`, `__job_industries`, `__job_types` | job × skill, place, industry or type | the silver bridge tables, plus `job_key` |
| staging | `stg_silver__ref_skills`, `stg_silver__ref_countries` | skill, country | the reference tables |
| intermediate | `int_job_postings` | job | jobs, plus `company_key`, `published_month`, the salary midpoint and `salary_is_plausible` |
| intermediate | `int_job_skill_pairs` | job × pair of skills | job skills joined to themselves |
| mart | `dim_date` | day | `dbt_utils.date_spine` from 2026-10-01 (the month of the first posting) to the day of the build |
| mart | `dim_skill`, `dim_industry` | skill, industry | reference tables and silver |
| mart | `dim_location` | place (city, country, region, Worldwide or unknown) | distinct places in `stg_silver__job_locations`, with the country name from `ref_countries` |
| mart | `dim_company` | company | distinct company names, with logo and first posting |
| mart | `dim_seniority` | level | seed `seniority_levels.csv` (Intern … Executive, Unspecified), with a sort order for charts |
| mart | `fct_job_postings` | job | `int_job_postings`: dates, company, seniority, remote, listed now, salaries, title, `url` |
| mart | `fct_job_skills` | job × skill | mentions, in title, plus the job's date, company and seniority keys, source, `is_listed_now` and `is_remote` |
| mart | `bridge_job_locations`, `bridge_job_industries`, `bridge_job_types` | job × place, industry or type | staging |
| mart | `agg_skill_demand_by_country_month` | month × place × skill | jobs per skill and place (country, or region for "EMEA"-style places) |
| mart | `agg_skill_co_occurrence` | pair of skills | jobs mentioning both |
| mart | `agg_salary_by_skill` | skill | median and quartiles of plausible yearly USD salaries |

The exact columns are settled model by model as they're written; the contracts then fix them.

## Tests

- **Sources:** unique and not-null keys, and freshness on `silver.jobs.built_at`: a warning after 1 day, an error after 2.
- **Staging and marts:** `unique` and `not_null` keys, `dbt_utils.unique_combination_of_columns` on bridges, `relationships` from facts and bridges to dimensions, and `accepted_values` for `source`, `seniority` and `location_type`.
- **Reconciliation:** one `fct_job_postings` row per silver job, one `fct_job_skills` row per silver job × skill.
- **Salary:** a singular test that warns when more than 5% of salaried jobs are implausible (`severity: warn`).
- **Contracts on the marts:** data types, `NOT NULL` and `CHECK`, which Databricks enforces, and primary and foreign keys, which are informational. They document the relationships and feed the ER diagram.

## Repo layout additions

```
dbt/job_listings/
    packages.yml, package-lock.yml       ← dbt_utils
    seeds/seniority_levels.csv
    models/staging/      _silver__sources.yml, _silver__models.yml, stg_silver__*.sql
    models/intermediate/ _int__models.yml, int_*.sql
    models/marts/        _marts__models.yml, dim_*.sql, fct_*.sql, bridge_*.sql, agg_*.sql
    tests/               assert_implausible_salary_share.sql
    README.md            ← how to run the project locally
docs/er-diagram.*        ← exported from DrawDB
```

## Concepts you'll meet
- **Model:** a `.sql` file holding one `SELECT`. dbt turns it into a view or table named after the file.
- **`source()` and `ref()`:** how a model names its inputs. `{{ source('silver', 'jobs') }}` is a table dbt doesn't build; `{{ ref('stg_silver__jobs') }}` is another model. From these, dbt knows the order to build in, the DAG.
- **Jinja:** the `{{ … }}` and `{% … %}` templating around the SQL. It fills in names, loops and macros before the SQL reaches Databricks.
- **Materialization:** view (the query runs each time it's read) or table (results stored), set per layer in `dbt_project.yml`.
- **Custom schema:** `+schema: staging` puts those models in `gold_staging`, while marts go to `gold`.
- **`dbt build`:** runs seeds, models and tests together in DAG order. A model's tests run right after it, and a failure stops what depends on it.
- **Tests:** *generic* tests (`unique`, `not_null`, `relationships`, `accepted_values`) are declared in YAML. *Singular* tests are SQL files that fail when they return rows. `severity: warn` reports without failing.
- **Seed:** a small CSV in the project, loaded as a table by `dbt seed`, for static lists like seniority order.
- **Package:** reusable macros and tests, here `dbt_utils`. They're installed with `dbt deps`.
- **Contract:** a mart's promised columns and types. With `enforced: true`, dbt refuses to build the model if the SQL's output differs, and it creates the declared constraints.
- **Grain:** what one row means ("one row per job × skill"). Getting it right is most of dimensional modelling.
- **Star schema:** *facts* (events or measures) at the centre, *dimensions* (descriptions) around them, and *bridges* for many-to-many relations.
- **`persist_docs`:** writes the YAML descriptions into Unity Catalog as table and column comments.

## Pitfalls
- **Silver must be built before dbt.** Locally, run the Databricks Job first when silver is stale; Phase 4 chains it.
- **Counting across bridges double-counts.** A job in two countries is two bridge rows, so "jobs" must be `count(distinct job_key)`. Also, totals over countries aren't the number of jobs.
- **Contracts need exact types:** `string`, `bigint`, `int`, `double`, `date`, `timestamp`, `boolean`. Silver's `times_seen` is a `bigint` (shown as LONG), and `mentions` an `int`.
- **Primary-key columns must be `NOT NULL`** before Databricks accepts the constraint.
- **Region-level places have no country:** "EMEA", "Europe" and "Worldwide" have a NULL `country_code` in `dim_location`. Filtering by country leaves them out, so regional and worldwide jobs are counted by `region` or `location_type`.
- **Name every constraint, and set `warn_unenforced: false` on primary and foreign keys.** Otherwise dbt-databricks warns on every build ("no `name` provided", "unenforced constraint type").
- **Enforced vs informational constraints:** Databricks enforces `not_null` and `check`, so those columns need no `not_null` test. Primary and foreign keys are only recorded, so `unique`, `unique_combination_of_columns` and `relationships` tests still check them. A foreign key needs the parent's primary key, which the `ref()` in `to:` guarantees by building the dimension first.
- **dbt never drops the table of a deleted model.** After renaming or removing a mart, drop its old table by hand (here `gold.dim_country`).
- **Dates are UTC**, as in silver.
- **A stale partial parse can hide new tests.** dbt reuses its last parse (`target/partial_parse.msgpack`), and dbt Power User re-parses in the background on every save. If a test or model you wrote is missing from the run, add `--no-partial-parse` once.
- **`dbt_utils.date_spine` leaves out the end date and returns timestamps.** `dim_date` passes `date_add(current_date(), 1)` as the end so today is included, and casts `date_day` to `date`.
- **`dbt_packages/`, `target/` and `logs/` are generated** and stay out of git (already in `.gitignore`). `package-lock.yml` is committed.
