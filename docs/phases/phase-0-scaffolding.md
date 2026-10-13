# Phase 0: Fix the scaffolding

**Goal:** a local environment where Airflow runs in Docker, can reach Databricks, can import our Python code and can run dbt. No pipeline logic yet; this phase only prepares the ground so Phases 1–4 can plug straight in.

**Done when:**
- `docker compose up -d` (from `airflow/`) starts Airflow with our custom image and the UI loads at http://localhost:8080.
- Inside the worker container, `dbt debug` connects to Databricks successfully.
- Inside the worker container, `python -c "import ingestion"` works.
- `dbt parse` runs on the host without the `example` config warning.
- Everything is committed on a branch and merged into `main`.

## Progress
- [ ] 0.1 Working branch
- [ ] 0.2 Custom Airflow image
- [ ] 0.3 Compose updates
- [ ] 0.4 dbt project config
- [ ] 0.5 Ingestion package
- [ ] 0.6 Split requirements
- [ ] 0.7 Env templates and README
- [ ] 0.8 Verify
- [ ] 0.9 Commit and merge

---

## Current state and problems

| Problem | Why it matters |
|---|---|
| Compose uses the stock `apache/airflow:3.3.2` image | It has no Databricks provider and no dbt, so Airflow can't trigger Databricks jobs or run dbt. |
| `airflow/.env` has no `DATABRICKS_*` values; they live in the root `.env` | Containers can't authenticate to Databricks. |
| Only `dags/`, `logs/`, `config/`, `plugins/` are mounted | Containers can't see `ingestion/` or `dbt/`. |
| `dbt_project.yml` configures a `models/example/` folder that doesn't exist | dbt prints a warning; the config doesn't describe our real layers. |
| `test.py` sits at the repo root | Scratch code; it should live in the ingestion package. |
| One root `requirements.txt` (a `pip freeze` of the local dbt env) | Airflow and dbt need different, conflicting dependency sets inside the image. |

**Kept as is:** the CeleryExecutor setup (Redis + worker, Flower optional). It already works, mirrors how Airflow runs in production, and RAM isn't a constraint on this machine.

---

## How the Airflow containers fit together

| Service | Role |
|---|---|
| `postgres` | Airflow's metadata database: DAG runs, task states, users, connections, variables |
| `redis` | Message queue (broker): the scheduler puts "run this task" messages here |
| `airflow-init` | One-off setup: creates/migrates the database and the admin user, then exits |
| `airflow-apiserver` | Web UI and REST API at http://localhost:8080 |
| `airflow-scheduler` | Decides which tasks are due and sends them to Redis |
| `airflow-dag-processor` | Reads the Python files in `dags/` and turns them into DAGs |
| `airflow-worker` | Picks tasks off Redis and **actually runs them** (our Python, dbt, Databricks calls) |
| `airflow-triggerer` | Runs "deferred" tasks that wait on something external without occupying a worker |
| `flower` (optional) | UI at http://localhost:5555 to watch Celery workers and queues; start with `--profile flower` |

All Airflow services share the `x-airflow-common` block, so a change to the image, mounts or env vars there applies to every one of them, including the worker.

---

## Tasks

### 0.1 Create a working branch
```
git checkout -b phase-0-scaffolding
```
All Phase 0 changes go here and are merged into `main` at the end. This is the habit for every phase.

### 0.2 Custom Airflow image: `airflow/Dockerfile`
Extend the official image instead of installing packages at container start (`_PIP_ADDITIONAL_REQUIREMENTS` reinstalls on every restart and is explicitly "for quick checks only").

What the Dockerfile does:
1. `FROM apache/airflow:3.3.2`.
2. Install into Airflow's own Python environment (`airflow/requirements.txt`):
   - `apache-airflow==3.3.2` (pinned so pip can't upgrade or downgrade Airflow while resolving)
   - `apache-airflow-providers-databricks` (operators to trigger Databricks jobs and SQL)
   - `databricks-sdk` (upload raw files to a Unity Catalog Volume in Phase 1)
   - `requests` (call the Jobicy API)
3. Create a **separate virtualenv** at `/opt/dbt-venv` and install dbt there (`dbt/requirements.txt`: `dbt-core`, `dbt-databricks`, same versions as the local env).

**Why a separate venv for dbt:** dbt and Airflow both pin libraries such as `protobuf`, `jinja2` and `sqlalchemy`, often to incompatible versions. Installing both into one environment either fails or silently breaks one of them. A separate venv gives dbt its own copy; Airflow calls it by path (`/opt/dbt-venv/bin/dbt`).

After the first successful build, pin the resolved versions of the provider and SDK in `airflow/requirements.txt` so rebuilds are reproducible.

### 0.3 Update `airflow/docker-compose.yaml`
All changes go in the shared `x-airflow-common` block:
- **Build our image:** replace `image: ${AIRFLOW_IMAGE_NAME:-apache/airflow:3.3.2}` with `build: .` plus `image: nexus-airflow:latest` (Compose builds it once and tags it with that name; every service reuses it).
- **Mount the project code** (containers read the same files you edit on the host, no rebuild needed):
  - `../ingestion:/opt/project/ingestion`
  - `../dbt:/opt/project/dbt`
  - add `PYTHONPATH: /opt/project` so DAGs can `import ingestion`.
- **Pass Databricks credentials:** add the root `.env` as a second `env_file` (`../.env`) so `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, etc. reach every container. `databricks-sdk` and our `profiles.yml` both read these variable names directly, so no extra config is needed. (An Airflow *connection* for the Databricks operators comes in Phase 2/4.)
- **dbt location:** add `DBT_PROFILES_DIR` and `DBT_PROJECT_DIR` pointing at `/opt/project/dbt/job_listings`.

### 0.4 Clean up the dbt project config
In `dbt/job_listings/dbt_project.yml`, replace the `example:` block with our layers:

```yaml
models:
  job_listings:
    staging:        # 1:1 cleanup of silver sources
      +materialized: view
      +schema: staging
    intermediate:   # joins and reusable logic
      +materialized: view
      +schema: staging
    marts:          # final dimension, fact and aggregate tables used by dashboards
      +materialized: table
```

- **view** = a saved query, recomputed each time it's read (cheap to build, fine for in-between steps).
- **table** = results stored physically (fast for dashboards).
- With dbt's default naming, `+schema: staging` produces a schema called `<DATABRICKS_SCHEMA>_staging` (e.g. `gold_staging`), keeping helper views out of the schema the dashboards use.

Create `models/staging/`, `models/intermediate/` and `models/marts/` (each with a `.gitkeep` so Git tracks the empty folder) and remove the unused `models/.gitkeep`.

### 0.5 Ingestion package
- Create `ingestion/__init__.py` (makes the folder an importable Python package).
- Move `test.py` to `ingestion/explore_api.py` with `git mv` (keeps its history). It stays a scratch script for poking at the API; the real client is written in Phase 1.

### 0.6 Split requirements
| File | Used by | Contents |
|---|---|---|
| `requirements.txt` (root, unchanged) | Your local venv | Existing freeze: dbt + Databricks libraries for running dbt from your machine |
| `airflow/requirements.txt` (new) | Airflow image | Airflow pin, Databricks provider, SDK, requests |
| `dbt/requirements.txt` (new) | dbt venv in the image | `dbt-core==1.12.5`, `dbt-databricks==1.12.7` |

### 0.7 Env templates and README
- `airflow/.env.example`: add a comment explaining Databricks values come from the root `.env`.
- `README.md`: short project description, prerequisites (Docker Desktop, Python, a Databricks workspace) and "how to start" steps:
  1. copy `.env.example` → `.env` and `airflow/.env.example` → `airflow/.env`, fill in values
  2. `cd airflow && docker compose build && docker compose up -d`
  3. open http://localhost:8080 (user/password `airflow` / `airflow`)
  4. optional: `docker compose --profile flower up -d` for Flower at http://localhost:5555
- Link this file from `docs/PLAN.md`.

### 0.8 Verify
1. `docker compose config`: Compose file parses, and the env values resolve.
2. `docker compose build`: image builds.
3. `docker compose up -d` then `docker compose ps`: all services `healthy`.
4. `docker compose exec airflow-worker /opt/dbt-venv/bin/dbt debug`: "All checks passed!" (proves dbt + Databricks credentials work where tasks will run).
5. `docker compose exec airflow-worker python -c "import ingestion, databricks.sdk; print('ok')"`.
6. On the host: `dbt parse` inside `dbt/job_listings` with no warnings.

### 0.9 Commit and merge
Commit in small logical steps (image, compose, dbt config, ingestion move, docs), then merge `phase-0-scaffolding` into `main` and push to GitHub.

---

## Concepts you'll meet in this phase

- **Dockerfile `FROM` / `RUN` / `USER` / `COPY`:** start from a base image, run commands to install things, switch the user commands run as, copy files into the image.
- **Image vs container:** the Dockerfile builds an image once; each `docker compose up` starts containers from it.
- **Bind mount (`host_path:container_path`):** a host folder appears inside the container; edits on either side are visible immediately.
- **`env_file`:** loads `KEY=value` lines from a file as environment variables in the container.
- **Executor:** the part of Airflow that decides *where* tasks run. With CeleryExecutor the scheduler queues tasks in Redis and worker containers pick them up; you could add more workers to run more tasks in parallel.
- **Virtualenv:** an isolated Python installation with its own packages.

## Pitfalls

- **Tasks run in `airflow-worker`.** When debugging a failing task, look at that container (`docker compose logs airflow-worker`) and test commands there, not in the scheduler.
- **Windows line endings:** `.gitattributes` already forces LF, which shell scripts in containers need. Don't change it.
- **Docker Desktop resources:** Airflow wants ≥4 GB RAM; check Settings → Resources.
- **Secrets:** `.env` and `airflow/.env` must never be committed (already in `.gitignore`). Double-check `git status` before each commit.
- **Port 8080 busy:** if something else uses it, change the left side of `"8080:8080"` in compose.
- **dbt writes `target/` and `logs/`** into the mounted project folder; both are gitignored.
