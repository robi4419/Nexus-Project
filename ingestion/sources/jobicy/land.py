"""Land the full Jobicy feed in the landing Volume: one JSON file per API page, saved byte for byte."""

from datetime import datetime

import requests
from databricks.sdk import WorkspaceClient

from ingestion.common import landing
from ingestion.sources.jobicy.client import SOURCE, fetch_pages


def land(
    session: requests.Session,
    ws: WorkspaceClient,
    volume: landing.LandingVolume,
    run_id: str,
    run_date: datetime,
) -> dict:
    """Fetch every page and write it to this run's folder. Returns a small summary (safe to pass through XCom)."""
    folder = landing.run_folder(volume, SOURCE, run_id, run_date)
    removed = landing.reset_folder(ws, folder)

    pages = jobs = 0
    pub_dates: list[str] = []
    for page in fetch_pages(session):
        landing.write_file(ws, f"{folder}/page_{page.number:03d}.json", page.raw)
        pages += 1
        jobs += len(page.jobs)
        pub_dates += [job["pubDate"] for job in page.jobs if job.get("pubDate")]

    return {
        "source": SOURCE,
        "folder": folder,
        "pages": pages,
        "jobs": jobs,
        "removed_files": removed,
        "oldest_pub_date": min(pub_dates, default=None),
        "newest_pub_date": max(pub_dates, default=None),
    }
