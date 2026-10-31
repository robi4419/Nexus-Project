# job_listings: the gold layer

This dbt project turns the **silver** tables (built by the Databricks Job `transform_jobs`) into **gold**: a star
schema of job postings and the skills they ask for, ready for the Power BI dashboards. Design decisions and their
reasons are in [`docs/phases/phase-3-dbt-models.md`](../../docs/phases/phase-3-dbt-models.md).

## What it builds

| Layer | Folder | Materialized as | Schema | Models |
|---|---|---|---|---|
| staging | `models/staging/` | views | `gold_staging` | `stg_silver__*`: one per silver table, plus surrogate keys |
| intermediate | `models/intermediate/` | views | `gold_staging` | `int_job_postings` (salary midpoint and plausibility), `int_job_skill_pairs` |
| marts | `models/marts/` | tables with enforced contracts | `gold` | `dim_*`, `fct_*`, `bridge_*`, `agg_*` |
| seed | `seeds/` | table | `gold_staging` | `seniority_levels`: the seniority scale and its sort order |

The marts form a star: `fct_job_postings` (one row per job) and `fct_job_skills` (job × skill) in the centre;
`dim_date`, `dim_skill`, `dim_location`, `dim_company`, `dim_industry` and `dim_seniority` around them; bridges for
the attributes a job can have several of (places, industries, job types). Every mart declares its column types,
`NOT NULL` and `CHECK` constraints (enforced by Databricks) and primary and foreign keys (informational, checked by
tests). Count jobs across a bridge with `count(distinct job_key)`.

## Setup

1. From the repo root, create the virtualenv and install the pinned packages (dbt-core 1.12.5, dbt-databricks 1.12.7,
   python-dotenv):
   ```
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in the `DATABRICKS_*` values. `profiles.yml` reads them from the environment;
   `DATABRICKS_SCHEMA=gold` makes the marts land in `gold` and staging in `gold_staging`. Never commit `.env`.
3. Install the dbt packages (`dbt_utils`, pinned in `package-lock.yml`):
   ```
   .venv\Scripts\dotenv.exe -f .env run -- .venv\Scripts\dbt.exe deps --project-dir dbt/job_listings --profiles-dir dbt/job_listings
   ```
4. Make sure silver is current: run the Databricks Job `transform_jobs` first if it's stale.

## Running it

Every evening Airflow runs `deps`, `source freshness` and `build` by itself (the `transform_and_build` DAG), with
the dbt in its own image. Running dbt by hand, as below, is for development.

`dotenv run` loads `.env` into one command. From the repo root in PowerShell (in Git Bash, use forward slashes):

```
.venv\Scripts\dotenv.exe -f .env run -- .venv\Scripts\dbt.exe <command> --project-dir dbt/job_listings --profiles-dir dbt/job_listings
```

| `<command>` | What it does |
|---|---|
| `build` | Seed, every model and every test, in dependency order. The normal way to run the project. |
| `build --select +agg_skill_co_occurrence` | One model plus everything it depends on (the `+` prefix). |
| `test --select marts` | Only the tests of the models in `models/marts/`. |
| `source freshness` | Warns when `silver.jobs` is more than a day old, fails after two. |
| `show --inline "select ..." --limit 20` | Runs a query and prints the result. `dbt show` adds its own `limit`, so don't end the query with one. |
| `docs generate`, then `docs serve --port 8081` | Builds the documentation site with the lineage graph and serves it on http://localhost:8081. The default port, 8080, is taken by the Airflow UI. |

## Tests

- **Keys and values:** `unique`, `not_null`, `accepted_values`, `relationships` and `dbt_utils.unique_combination_of_columns`.
- **Reconciliation:** `dbt_utils.equal_rowcount` checks one `fct_job_postings` row per silver job and one
  `fct_job_skills` row per silver job × skill.
- **Salary warning:** `tests/assert_implausible_salary_share.sql` **warns** (doesn't fail) when more than 5% of the
  salaried jobs have an implausible salary. The limit is the variable `max_implausible_salary_share` in
  `dbt_project.yml`; override it for one run with `--vars "{max_implausible_salary_share: 0.005}"`.

## Documentation

Every model and column has a description. Columns that appear in several layers take theirs from the doc blocks in
[`models/_docs.md`](models/_docs.md), so each text is written once. `persist_docs` writes the descriptions into Unity
Catalog as table and column comments on every build.

## Things to know

- **Run a full `build` after silver changes.** Staging and intermediate are views that read silver live, while marts
  are tables from their last build; rebuilding one mart alone can mix the two moments.
- **dbt never drops the table of a deleted or renamed model.** Drop the old table by hand.
- **A model or test missing from a run?** dbt reuses its last parse; add `--no-partial-parse` once.
- **Dates are UTC.**
