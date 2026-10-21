"""Land the full Arbeitnow feed in the landing Volume: one JSON file per API page, saved byte for byte."""

from datetime import datetime, timezone

import requests
from databricks.sdk import WorkspaceClient

from ingestion.common import landing
from ingestion.sources.arbeitnow.client import PAGE_DELAY, SOURCE, fetch_pages


def land(
    session: requests.Session,
    ws: WorkspaceClient,
    volume: landing.LandingVolume,
    run_id: str,
    run_date: datetime,
    delay: float = PAGE_DELAY,
) -> dict:
    """Fetch every page (`delay` seconds apart) and write it to this run's folder. Returns a small summary (safe to
    pass through XCom)."""
    folder = landing.run_folder(volume, SOURCE, run_id, run_date)
    removed = landing.reset_folder(ws, folder)

    pages = jobs = remote = 0
    slugs: set[str] = set()
    created: list[int] = []
    for page in fetch_pages(session, delay=delay):
        landing.write_file(ws, f"{folder}/page_{page.number:03d}.json", page.raw)
        pages += 1
        jobs += len(page.jobs)
        remote += sum(1 for job in page.jobs if job.get("remote"))
        slugs |= {job["slug"] for job in page.jobs if job.get("slug")}
        created += [job["created_at"] for job in page.jobs if job.get("created_at")]

    return {
        "source": SOURCE,
        "folder": folder,
        "pages": pages,
        "jobs": jobs,
        # The feed updates hourly, so a job can move to another page during the download and be seen twice.
        "distinct_jobs": len(slugs),
        "remote_jobs": remote,
        "removed_files": removed,
        "oldest_created_at": _iso(min(created, default=None)),
        "newest_created_at": _iso(max(created, default=None)),
    }


def _iso(unix_seconds: int | None) -> str | None:
    """Arbeitnow's created_at (seconds since 1970, UTC) as readable text, e.g. '2026-10-20T15:00:57+00:00'."""
    return None if unix_seconds is None else datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()
