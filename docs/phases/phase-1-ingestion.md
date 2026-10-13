# Phase 1: Ingestion

**Goal:** an Airflow DAG that, once a day, downloads every job currently in the Jobicy feed and saves the API responses, untouched, as files in a Databricks Unity Catalog Volume. Nothing is cleaned or parsed yet; that's Phase 2. The point is to start collecting history as early as possible.

**Done when:**
- Unit tests for the Jobicy client and the Volume writer pass locally.
- The `jobicy_pipeline` DAG loads in Airflow without import errors.
- A manual run of the DAG lands one JSON file per API page in the Volume, and its summary task reports a sensible job count.
- Re-running the same DAG run replaces its files instead of duplicating them.
- The DAG is unpaused, so it runs daily from now on.

## Progress
- [ ] 1.1 Branch and config
- [ ] 1.2 Jobicy API client
- [ ] 1.3 Volume writer
- [ ] 1.4 Unit tests
- [ ] 1.5 Airflow DAG
- [ ] 1.6 Verify end to end
- [ ] 1.7 Commit, PR and merge

---

## What we know about the API

From Jobicy's documentation ([github.com/Jobicy/remote-jobs-api](https://github.com/Jobicy/remote-jobs-api)) and a test pull on 2026-10-13:

| Fact | Consequence for the design |
|---|---|
| Endpoint `GET https://jobicy.com/api/v2/remote-jobs`, no API key | Nothing secret to manage for ingestion. |
| `count` accepts 1–200 jobs per page | Use 200: the whole feed is only a handful of requests. |
| Paging: each response has `hasMore` and `nextCursor`; pass `cursor=<nextCursor>` to get the next (older) page. Cursors expire after 24 h. | Follow cursors until `hasMore` is false. A retry starts again from page 1 rather than reusing an old cursor. |
| **The feed only covers jobs published in the last 7 days** | Fetch the whole window every run. A job seen on several days is deduplicated later (Phase 2, by `id`). If Airflow is down for less than a week, nothing is lost. |
| Size on 2026-10-13: **787 jobs, 4 pages, ~6.6 MB** | Small enough to download the full window each run; no need to remember where the last run stopped. |
| Fair use: no more than one sync per hour; retry HTTP 429 after the `Retry-After` header | A daily schedule is well inside the limit; the client retries politely. |
| Terms: keep Jobicy as the source and keep each job's `url` | Store `url`; dashboards link back to the original posting. |
| Extra endpoints: `?get=locations`, `?get=industries`, and `/remote-jobs/status?ids=...` (active/closed) | Useful later: location and industry lists for Phase 2 normalisation, job status for "how long does a job stay open" in Phase 7. |

Profile of that test pull (useful for Phase 2): every job had `id`, `jobTitle`, `companyName`, `jobIndustry`, `jobType`, `jobGeo`, `jobLevel`, `jobDescription` and `pubDate`; 54% had salary fields. `jobGeo` is free text (`USA`, `Canada,  USA` with a double space, `EMEA`, `Anywhere`); `jobLevel` values were `Senior`, `Director`, `Any`, `Midweight`, `Entry-Level, Junior`.

### Change from the original plan
`docs/PLAN.md` mentioned a *watermark* (remembering the newest job already fetched). It isn't needed: the feed is only 7 days long and fits in 4 requests, so each run takes the whole window and Phase 2 removes duplicates. Fewer moving parts, and nothing to break if a run is skipped.

---

## Where the files go

```
/Volumes/<catalog>/bronze/landing/jobicy/
    ingest_date=2026-10-13/
        run=scheduled__2026-10-13T06-00-00/
            page_001.json      ← exact API response body for page 1
            page_002.json
            ...
```

- **Catalog** comes from `DATABRICKS_CATALOG` in `.env` (currently `workspace`).
- **Schema `bronze`** and **Volume `landing`** are created by the DAG if they don't exist (defaults, overridable with `DATABRICKS_LANDING_SCHEMA` / `DATABRICKS_LANDING_VOLUME`). The `bronze` schema will also hold the Phase 2 bronze table.
- **One file per API page, saved byte for byte.** The response also carries `lastUpdate` and `apiVersion`, which stay with the data.
- **`ingest_date=` and `run=` folders** use `key=value` naming. Spark recognises this pattern and can turn the folder names into columns when reading (Phase 2), so each row knows when it was fetched.
- **One folder per DAG run.** A retry or re-run of the same DAG run clears and rewrites that folder, so there are never duplicate or half-finished files from one run.

---

## Tasks

### 1.1 Branch and config
- Branch `phase-1-ingestion` (created).
- Optional settings in `.env.example`: `DATABRICKS_LANDING_SCHEMA=bronze`, `DATABRICKS_LANDING_VOLUME=landing`. The code uses these defaults when they're absent, so your `.env` doesn't need changing.
- Add `pytest` to the root `requirements.txt` (local development only).

### 1.2 Jobicy API client: `ingestion/jobicy_client.py`
A small module with no Airflow or Databricks code in it, so it can be tested on its own.
- A `requests.Session` with:
  - **automatic retries** for HTTP 429 and 5xx errors, waiting longer each time (*exponential backoff*) and honouring `Retry-After`;
  - a **timeout** on every request, so a hung connection can't block the task forever;
  - a `User-Agent` that names the project.
- `fetch_pages(...)` walks the feed: request `count=200`, yield the page, then follow `nextCursor` while `hasMore` is true. Each yielded page includes the **raw response bytes** (to save) and the parsed JSON (to read `hasMore`, `nextCursor` and the job count).
- Safety checks:
  - stop with an error if `success` is false;
  - stop after `max_pages` (default 20) in case the API ever loops;
  - a page with zero jobs ends the walk.

### 1.3 Volume writer: `ingestion/landing.py`
Uses `databricks-sdk`'s `WorkspaceClient`, which reads `DATABRICKS_HOST` and `DATABRICKS_TOKEN` from the environment automatically.
- `ensure_volume(...)`: create the `bronze` schema and the `landing` Volume if missing (get-or-create, safe to run every time).
- `run_folder(...)`: build the `ingest_date=.../run=...` path; the run ID is made safe for paths (no `:` or `+`).
- `reset_folder(...)`: delete files left by an earlier attempt of the same run.
- `write_file(...)`: upload bytes to a Volume path with the SDK's Files API.
- `land_jobicy_feed(...)`: ties it together (fetch each page, write `page_NNN.json`) and returns a **small summary**: run folder, page count, job count, newest and oldest `pubDate`.

### 1.4 Unit tests: `tests/`
Run locally with `pytest`, no network or Databricks needed.
- `tests/fixtures/jobicy_page.json`: a trimmed real response (2 jobs, short descriptions).
- **Client tests** with a fake session that returns prepared responses:
  - follows the cursor across pages and stops when `hasMore` is false;
  - stops at `max_pages`;
  - raises when `success` is false;
  - passes `count` and `cursor` correctly.
- **Writer tests** with a fake `WorkspaceClient` that records calls:
  - path layout and run-ID cleanup;
  - files written per page;
  - the folder is cleared before writing;
  - the summary counts are right.

### 1.5 Airflow DAG: `airflow/dags/jobicy_pipeline.py`
Written with the Airflow 3 **TaskFlow** style (`@dag` and `@task` decorators from `airflow.sdk`).

```
ensure_landing_volume  ──►  fetch_and_land  ──►  check_run
```

| Task | Does | Returns (via XCom) |
|---|---|---|
| `ensure_landing_volume` | Get-or-create the schema and Volume | Volume base path |
| `fetch_and_land` | Clear this run's folder, fetch every page, write each to the Volume | Small summary dict |
| `check_run` | Fail if 0 jobs were landed; log the summary | — |

DAG settings:
- `schedule="0 6 * * *"`: daily at 06:00 UTC.
- `catchup=False`: the API can only return the current window, so there's no point "catching up" on past dates.
- `max_active_runs=1`: no overlapping runs.
- `retries=2`, 10 minutes apart.
- `tags=["jobicy", "ingestion"]`.

**Why fetching and saving are one task:** tasks can only pass data to each other through **XCom**, which is stored in Airflow's Postgres database and meant for small values (IDs, paths, counts). Passing 6.6 MB of JSON through it is a known anti-pattern. With Celery, the next task might also run on a different worker, so saving to a local temp file isn't safe either. So `fetch_and_land` streams pages straight to the Volume and only passes a tiny summary on.

**No work at the top level of the DAG file.** Airflow re-reads DAG files every few seconds. API calls or Databricks connections belong inside tasks, never at import time.

The DAG is created **paused** (the compose setting `DAGS_ARE_PAUSED_AT_CREATION`), so nothing runs until you switch it on.

### 1.6 Verify end to end
1. `pytest` passes locally.
2. `docker compose exec airflow-scheduler airflow dags list-import-errors` shows nothing.
3. In the UI, trigger `jobicy_pipeline` manually; all three tasks go green.
4. The files appear in Databricks: **Catalog → workspace → bronze → Volumes → landing**. The page count and job count match the `check_run` log.
5. Clear `fetch_and_land` for that run and let it re-run: the folder is rewritten, not duplicated.
6. Unpause the DAG so it runs daily.

### 1.7 Commit, PR and merge
Small commits (config, client, writer, tests, DAG, docs), push the branch, open a PR, merge, update local `main`.

---

## Concepts you'll meet in this phase

- **REST API:** a web address that returns data (JSON) instead of a web page. You call it with HTTP `GET` and query parameters (`?count=200&cursor=...`).
- **Pagination with a cursor:** big results come in pages; the response hands you a bookmark (`nextCursor`) to ask for the next one.
- **Retries and exponential backoff:** on a temporary error, wait and try again, doubling the wait each time, so a struggling server isn't hammered.
- **HTTP 429 / `Retry-After`:** "too many requests"; the server tells you how long to wait.
- **Idempotency:** running something twice has the same result as running it once. Our run folders make the DAG idempotent per run.
- **TaskFlow API:** write tasks as normal Python functions with `@task`. Return values are passed to downstream tasks automatically through XCom.
- **XCom:** Airflow's small message-passing store between tasks.
- **Cron schedule:** `0 6 * * *` means minute 0, hour 6, every day, every month, every weekday.
- **`catchup`:** whether Airflow creates runs for every missed interval since `start_date`.
- **Unity Catalog names:** `catalog.schema.object` (e.g. `workspace.bronze.landing`). A **Volume** is a governed folder for files, at `/Volumes/<catalog>/<schema>/<volume>/`.
- **pytest, fixtures and fakes:** tests are functions starting with `test_`; a fixture is prepared test data; a fake replaces a real service (the API, Databricks) so tests run fast and offline.

## Pitfalls

- **Polling limit:** don't schedule more often than hourly; daily is plenty with a 7-day window.
- **Airflow 3 manual runs have no `logical_date`.** Folder names use the DAG run's ID and start time instead.
- **Big data in XCom:** keep return values small (see 1.5).
- **Top-level code in DAG files:** runs on every parse; keep it to imports and definitions.
- **Code changes in `ingestion/`** are picked up by tasks on their next run (the folder is mounted), but a new Python package needs an image rebuild.
- **Databricks permissions:** the token's user needs permission to create schemas in the catalog. If `ensure_landing_volume` fails with a permission error, create `bronze` and `landing` once in the Databricks UI instead.
