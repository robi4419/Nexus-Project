"""Land one day of exchange rates in the landing Volume: one JSON file per run, saved byte for byte."""

from datetime import datetime

import requests
from databricks.sdk import WorkspaceClient

from ingestion.common import landing
from ingestion.sources.frankfurter.client import SOURCE, fetch_rates


def land(
    session: requests.Session,
    ws: WorkspaceClient,
    volume: landing.LandingVolume,
    run_id: str,
    run_date: datetime,
) -> dict:
    """Fetch the rates for the run's date and write them to this run's folder. Returns a small summary."""
    folder = landing.run_folder(volume, SOURCE, run_id, run_date)
    removed = landing.reset_folder(ws, folder)

    rates = fetch_rates(session, run_date.date())
    landing.write_file(ws, f"{folder}/rates.json", rates.raw)

    return {
        "source": SOURCE,
        "folder": folder,
        "requested_date": run_date.date().isoformat(),
        "rate_date": rates.rate_date.isoformat(),
        "currencies": sorted(rates.rates),
        "removed_files": removed,
    }
