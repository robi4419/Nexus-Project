# Phase 4: Orchestration end to end

**Goal:** the whole pipeline runs every day with no manual step. The three job ingestion DAGs land their files; once all three have, Airflow starts the Databricks Job `transform_jobs` (bronze and silver), waits for it, then runs dbt (gold). Any failure sends an email.

**Done when:**
- A normal day runs untouched: the three ingestion DAGs at 18:00 UTC, then `transform_and_build`. The Databricks Job and `dbt build` are green, and gold is rebuilt from that day's silver.
- A failed run of any DAG sends an email to the alert address, tested on purpose.
- The DAGs import without errors, and `airflow dags test transform_and_build` passes.
- Running `transform_and_build` twice in a row changes nothing (same row counts).
- `pytest` still passes.

## Progress
- [x] 4.1 Branch, plan doc, `PLAN.md`
- [x] 4.2 Settings: Airflow connections for Databricks and Gmail built from `.env`, the Job's name, dbt's working folders in the containers
- [x] 4.3 Ingestion DAGs update their Asset only after their run's check passes
- [x] 4.4 New DAG `transform_and_build`: Databricks Job, then dbt (deps, source freshness, build)
- [ ] 4.5 Failure emails for every DAG, plus a manual `alert_test` DAG
- [x] 4.6 Retries and time limits (written into `transform_and_build` in 4.4)
- [ ] 4.7 Verify: import check, `airflow dags test`, a real daily cycle, a forced failure, a rerun
- [ ] 4.8 Docs, commit, PR and merge

---

## Starting point (2026-10-30)

| Area | State |
|---|---|
| Airflow | 3.3.2 in Docker (CeleryExecutor), custom image `nexus-airflow` with `apache-airflow-providers-databricks` 7.22.0 and `apache-airflow-providers-smtp` 3.0.4. UI on http://localhost:8080. |
| Ingestion | `ingest_jobicy`, `ingest_arbeitnow` and `ingest_himalayas` daily at 18:00 UTC; `ingest_fx_rates` on weekdays at 17:00 with catchup. Each marks the Asset `landing/<source>` when `fetch_and_land` succeeds. Tasks retry twice, 10 minutes apart. |
| Silver | Databricks Job `[dev robix4000] transform_jobs` (ID 486383826742084), deployed from the bundle in development mode, started by hand. |
| Gold | dbt 1.12.5 in the image's own virtualenv, `/opt/dbt-venv/bin/dbt`; `dbt/` is mounted at `/opt/project/dbt`, and `DBT_PROJECT_DIR` and `DBT_PROFILES_DIR` point at it. Run by hand from the local `.venv` so far. |
| Secrets | `.env` (gitignored) holds the Databricks host and token; docker-compose passes it to every container. |

## Decisions (2026-10-30)

1. **One new DAG, `transform_and_build`, scheduled on the three job Assets together:** `landing/jobicy & landing/arbeitnow & landing/himalayas`. It runs once a day, about 15 minutes after the 18:00 ingestion, when all three have landed. If a source fails, the chain waits until that source lands (its failure email says why). Exchange rates aren't part of the condition: they land only on weekdays, and silver uses the latest rate on or before each job's date anyway. Rejected:
   - any source landed: up to three Databricks runs a day, against Free Edition's compute limits;
   - a fixed time: it would run on top of a failed or late ingestion.
2. **dbt runs as plain commands in Bash tasks** calling `/opt/dbt-venv/bin/dbt`: `deps`, then `source freshness`, then `build`. dbt orders the models itself, a build takes about 3 minutes, and each step has one log. Rejected: astronomer-cosmos (one Airflow task per model). Each task would start dbt again, which is much slower, and it's another package that must keep up with Airflow 3.3.
3. **Failures are emailed through Gmail** with Airflow's `SmtpNotifier`, from a Gmail **app password**. One email per failed DAG run, for all five DAGs. The address, user and app password live in `.env` only.
4. **The Databricks Job is started with the provider's `DatabricksRunNowOperator`, deferrable.** While the Job runs (about 10 minutes), the waiting is handed to Airflow's triggerer, so no worker slot is held. The task also gets a link to the Databricks run in the UI. Rejected: calling the SDK from a Python task, which would hold a worker for the whole run.
5. **Assets are updated only after a run's checks pass.** The `outlets` move from `fetch_and_land` to `check_run` in the ingestion DAGs, so a run that landed nothing usable never starts the transform.
6. **Connections come from `.env` through docker-compose,** as `AIRFLOW_CONN_DATABRICKS_DEFAULT` and `AIRFLOW_CONN_SMTP_DEFAULT` environment variables built from values already there. Nothing is typed into the UI, and rotating the Databricks token stays one `.env` change plus `docker compose up -d`.
7. **The Job is found by name,** from `DATABRICKS_TRANSFORM_JOB_NAME` in `.env`. The development-mode name carries the user name, so it stays out of the code; a name also survives a redeploy that changes the ID.

## How the pipeline runs (from 4.4)

```
18:00 UTC  ingest_jobicy ───────┐
18:00 UTC  ingest_arbeitnow ────┼─ all three Assets updated ─►  transform_and_build
18:00 UTC  ingest_himalayas ────┘                                 run_transform_job   Databricks Job (deferrable)
17:00 UTC  ingest_fx_rates (weekdays; not a condition)            dbt_deps
                                                                  dbt_source_freshness
                                                                  dbt_build           gold: 13 marts, 85 tests
any DAG fails ─► email to ALERT_EMAIL
```

## Tasks

### 4.2 Settings
- **`.env` (you add the values; `.env.example` gets empty placeholders):**
  - `DATABRICKS_TRANSFORM_JOB_NAME="[dev robix4000] transform_jobs"`;
  - `SMTP_USER` (the Gmail address), `SMTP_PASSWORD` (the 16-character app password), `ALERT_EMAIL` (where alerts go).
- **`docker-compose.yaml`, in the environment shared by every Airflow container:**
  - `AIRFLOW_CONN_DATABRICKS_DEFAULT`: JSON with `conn_type` databricks, the host, and the token as password;
  - `AIRFLOW_CONN_SMTP_DEFAULT`: JSON with `smtp.gmail.com`, port 465 (SSL), the user and the app password, and `disable_tls`;
  - `DBT_TARGET_PATH` and `DBT_LOG_PATH` under `/tmp`, so container runs don't overwrite the `target/` and `logs/` folders that local runs use (the `dbt/` folder is shared with Windows).
- Recreate the containers with `docker compose up -d`, and check both connections from the worker with the provider hooks: `DatabricksHook().find_job_id_by_name(…)` and `SmtpHook()` (login only). On 2026-10-30 the Job resolved to ID 486383826742084 and the Gmail login succeeded.

### 4.3 Assets after checks
In `ingest_jobicy`, `ingest_arbeitnow`, `ingest_himalayas` and `ingest_fx_rates`, move `outlets=[LANDING_ASSET]` from `fetch_and_land` to `check_run`.

### 4.4 `transform_and_build`
- `schedule=(Asset("landing/jobicy") & Asset("landing/arbeitnow") & Asset("landing/himalayas"))`, `max_active_runs=1`.
- `run_transform_job`: `DatabricksRunNowOperator(job_name=…, deferrable=True)`.
- `dbt_deps`, `dbt_source_freshness`, `dbt_build`: Bash tasks with `/opt/dbt-venv/bin/dbt`. Freshness guards against a Job that "succeeded" without rebuilding silver.
- **First run, `airflow dags test transform_and_build` on 2026-10-30:** succeeded in 7.5 minutes. The Databricks task deferred for about 4 minutes while the Job ran, then freshness passed and `dbt build` passed 108 of 108.

### 4.5 Failure emails
- A shared helper returns an `SmtpNotifier` with the DAG, the run and a link to it in the UI. Every DAG sets `on_failure_callback` to it, so there's one email per failed run, after retries.
- `alert_test`: a manual DAG with no schedule whose only task fails on purpose, to check emails arrive (useful again after changing the app password).

### 4.6 Retries and time limits
- Databricks task: 1 retry (the Job is idempotent: bronze loads only new files, silver and gold are rebuilt) and a 1-hour `execution_timeout`.
- dbt tasks: 1 retry (for example, a SQL warehouse slow to start) and a 30-minute limit.
- Ingestion keeps its 2 retries.

### 4.7 Verify
1. `airflow dags list-import-errors` is empty, and all five DAGs are listed.
2. `airflow dags test transform_and_build` runs the chain once, outside the scheduler.
3. Trigger `alert_test`: an email arrives.
4. Unpause `transform_and_build`. After 18:00 UTC it starts by itself once the three ingestions finish, and everything is green.
5. Trigger it again by hand: silver and gold row counts don't change.
6. `pytest` passes.

## Backfill and reruns

Classic Airflow backfill (re-running past dates) mostly doesn't apply here, and nothing is lost when the PC is off:
- **Job sources can't serve the past.** But each run catches up by itself: Jobicy's feed covers the last 7 days, Arbeitnow sends its whole feed, and Himalayas continues from the previous run's newest job. `run_immediately=True` starts a missed 18:00 run when Airflow comes back.
- **Exchange rates backfill already:** `ingest_fx_rates` has `catchup=True`.
- **Transform and dbt rebuild everything** from bronze and silver, so "backfilling" them means one rerun. Trigger `transform_and_build` by hand after fixing a failure.

## Concepts you'll meet
- **Asset-aware scheduling:** a DAG scheduled on Assets runs when other DAGs' tasks update them. `&` waits for all of them (since its last run), and `|` runs on any one.
- **Deferrable operator and triggerer:** a task that waits on something external suspends itself, and the triggerer service (already in docker-compose) checks on it with little memory, resuming the task on a worker when it's done.
- **Connection:** host, credentials and options Airflow uses to reach a system, by ID (`databricks_default`, `smtp_default`). An environment variable `AIRFLOW_CONN_<ID>` holding JSON defines one without the UI.
- **Callback and notifier:** `on_failure_callback` runs code when a DAG run fails; a *notifier* such as `SmtpNotifier` is a ready-made callback that sends a message, with Jinja templates for the text.
- **`execution_timeout`:** the longest a task may run before Airflow fails it.
- **docker-compose interpolation:** `${VAR}` in `docker-compose.yaml` is filled from the `.env` file next to it when the containers are created, so changing `.env` needs `docker compose up -d`.
- **Idempotent:** running it again gives the same result, which makes retries and reruns safe.

## Pitfalls
- **A Gmail app password works only with 2-step verification on,** and Google revokes it when the account password changes. It can read and send mail, so it stays in `.env` and can be revoked any time in the Google account.
- **Port 465 is encrypted from the start, so the SMTP connection needs `"disable_tls": true`.** Otherwise the hook also tries STARTTLS (meant for plain connections on port 587), and Gmail answers "STARTTLS extension not supported by server".
- **Save `.env` before `docker compose up -d`.** Containers read it only when they're created; a value added later needs another `up -d`.
- **DAG-level callbacks run in the DAG processor,** not on the worker, so the SMTP connection must reach every Airflow container (it does, through the shared environment).
- **The Job's name follows the bundle target.** Deploying another target (or a different user deploying) changes it; update `DATABRICKS_TRANSFORM_JOB_NAME`.
- **The Asset condition waits for all three sources.** One source down for days holds back silver and gold; its failure emails are the signal.
- **Rotating the Databricks token** now also updates the Airflow connection, through the same `docker compose up -d`.
- **Airflow only runs while the PC and Docker are on.** Missed 18:00 runs start when Airflow comes back.
- **Free Edition limits:** one Databricks run a day stays well within them; avoid triggering the chain many times in a row.

## Repo layout additions

```
airflow/dags/
    transform_and_build.py     ← Databricks Job, then dbt
    alert_test.py              ← manual DAG that fails on purpose
    common/alerts.py           ← the shared failure notifier (folder name may change in 4.5)
docker-compose.yaml            ← connections and dbt paths in the shared environment
.env.example                   ← new placeholders
```
