"""Land new and updated Tech jobs from the Himalayas feed in the landing Volume, and delete them once they expire.

Unlike Jobicy and Arbeitnow, a run doesn't download the whole feed (about 128,000 jobs). It walks the feed newest
first back to a cutoff and keeps only the Tech categories. The jobs are written in one file per UTC day on which
they expire (`expires_2026-12-19.json`, …), so the files aren't the API's pages byte for byte. Deleting a file then
removes exactly the jobs that expire that day, as the API terms require. A `manifest.json`, written last, records the
cutoff and the newest job seen; the next run starts from there.
"""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

import requests
from databricks.sdk import WorkspaceClient

from ingestion.common import landing
from ingestion.sources.himalayas.client import REQUEST_DELAY, SOURCE, fetch_pages

log = logging.getLogger(__name__)

# The parentCategories kept (decision 5). A job without any parent category is left out.
TECH_CATEGORIES = frozenset(
    {"Developer", "Data Science", "Product", "Design", "Hardware Engineer", "Research & Development"}
)
# About 3,300 jobs are updated a day, so each day back is about 165 pages, or 5 minutes.
FIRST_RUN = timedelta(days=2)  # how far back the very first run goes
# Each run re-reads the day before the previous run's newest job, in case the feed's daily refresh adds jobs whose
# pubDate is a little older than what the previous run already saw.
OVERLAP = timedelta(days=1)
MAX_LOOKBACK = timedelta(days=7)  # after a long break (PC off), catch up at most this far
LOG_EVERY = 100  # pages between progress lines in the task log
MANIFEST = "manifest.json"
_EXPIRY_FILE = re.compile(r"/expires_(\d{4}-\d{2}-\d{2})\.json$")


def land(
    session: requests.Session,
    ws: WorkspaceClient,
    volume: landing.LandingVolume,
    api_key: str,
    run_id: str,
    run_date: datetime,
    now: datetime | None = None,
    delay: float = REQUEST_DELAY,
) -> dict:
    """Fetch the jobs updated since the cutoff, write the Tech ones by expiry day and then the manifest to this run's
    folder. Returns the manifest (safe to pass through XCom: it holds no key and no job data)."""
    now = now or datetime.now(timezone.utc)
    folder = landing.run_folder(volume, SOURCE, run_id, run_date)
    cutoff, cutoff_from = _cutoff(ws, volume, folder, now)
    removed = landing.reset_folder(ws, folder)
    last_purged_day = _last_purged_day(now)

    pages = tech_jobs = skipped = 0
    pub_dates: list[int] = []
    by_expiry_day: dict[date, list[dict]] = {}
    for page in fetch_pages(session, api_key, stop_before=cutoff, delay=delay):
        pages += 1
        if pages % LOG_EVERY == 0:
            log.info("page %s: reached %s (cutoff %s)", pages, _iso(page.oldest_pub_date), _iso(cutoff))
        pub_dates += [job["pubDate"] for job in page.jobs]
        for job in page.jobs:
            if job["pubDate"] < cutoff or not _is_tech(job):
                continue
            day = _expiry_day(job)
            if day <= last_purged_day:  # the purge would delete it straight away
                skipped += 1
                continue
            by_expiry_day.setdefault(day, []).append(job)
            tech_jobs += 1
    for day, jobs in sorted(by_expiry_day.items()):
        landing.write_file(ws, f"{folder}/expires_{day.isoformat()}.json", _to_json(jobs))

    manifest = {
        "source": SOURCE,
        "folder": folder,
        "cutoff": _iso(cutoff),
        "cutoff_from": cutoff_from,
        "pages": pages,
        "jobs_seen": len(pub_dates),
        "tech_jobs": tech_jobs,
        "skipped_expiring": skipped,
        "files": len(by_expiry_day),
        "removed_files": removed,
        "newest_pub_date": _iso(max(pub_dates, default=None)),
        "oldest_pub_date": _iso(min(pub_dates, default=None)),
    }
    landing.write_file(ws, f"{folder}/{MANIFEST}", json.dumps(manifest, indent=2).encode("utf-8"))
    return manifest


def purge_expired(ws: WorkspaceClient, volume: landing.LandingVolume, now: datetime | None = None) -> dict:
    """Delete every landed job file whose expiry day is tomorrow or earlier: up to a day early, never late. Manifests
    stay: they hold no job data, and the newest one is the next run's starting point."""
    last_day = _last_purged_day(now or datetime.now(timezone.utc))
    deleted = kept = 0
    for date_folder in landing.list_subfolders(ws, f"{volume.path}/{SOURCE}"):
        for run_folder in landing.list_subfolders(ws, date_folder):
            for path in landing.list_files(ws, run_folder):
                found = _EXPIRY_FILE.search(path)
                if not found:
                    continue
                if date.fromisoformat(found[1]) <= last_day:
                    ws.files.delete(path)
                    deleted += 1
                else:
                    kept += 1
    return {"source": SOURCE, "deleted_through": last_day.isoformat(), "deleted_files": deleted, "kept_files": kept}


def _last_purged_day(now: datetime) -> date:
    """Jobs expiring on this UTC day or earlier are deleted (and not landed): tomorrow, so a daily purge is never late."""
    return (now.astimezone(timezone.utc) + timedelta(days=1)).date()


def _expiry_day(job: dict) -> date:
    return datetime.fromtimestamp(job["expiryDate"], tz=timezone.utc).date()


def _cutoff(ws: WorkspaceClient, volume: landing.LandingVolume, folder: str, now: datetime) -> tuple[int, str]:
    """Where this run's walk stops (Unix seconds), and why."""
    own = _read_manifest(ws, folder)
    if own:
        # This run already finished once and is being run again (an Airflow Clear): fetch the same range again.
        return _seconds(own["cutoff"]), "earlier attempt of this run"
    previous = _latest_manifest(ws, volume, exclude=folder)
    if previous is None:
        return int((now - FIRST_RUN).timestamp()), "first run"
    cutoff = _seconds(previous["newest_pub_date"]) - int(OVERLAP.total_seconds())
    floor = int((now - MAX_LOOKBACK).timestamp())
    if cutoff < floor:
        return floor, "7-day limit"
    return cutoff, "previous run"


def _latest_manifest(ws: WorkspaceClient, volume: landing.LandingVolume, exclude: str) -> dict | None:
    """The manifest of the finished run that saw the newest job, looking at the newest ingest_date folders first. A run
    that failed midway wrote no manifest, so it doesn't count."""
    for date_folder in reversed(landing.list_subfolders(ws, f"{volume.path}/{SOURCE}")):
        manifests = [
            manifest
            for run_folder in landing.list_subfolders(ws, date_folder)
            if run_folder != exclude
            and (manifest := _read_manifest(ws, run_folder))
            and manifest.get("newest_pub_date")
        ]
        if manifests:
            return max(manifests, key=lambda manifest: _seconds(manifest["newest_pub_date"]))
    return None


def _read_manifest(ws: WorkspaceClient, folder: str) -> dict | None:
    data = landing.read_file(ws, f"{folder}/{MANIFEST}")
    return json.loads(data) if data else None


def _is_tech(job: dict) -> bool:
    return not TECH_CATEGORIES.isdisjoint(job.get("parentCategories") or [])


def _to_json(jobs: list[dict]) -> bytes:
    return json.dumps({"jobs": jobs}, ensure_ascii=False).encode("utf-8")


def _iso(unix_seconds: int | None) -> str | None:
    """Unix seconds as readable UTC text, e.g. '2026-10-20T15:22:07+00:00'."""
    return None if unix_seconds is None else datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()


def _seconds(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())
