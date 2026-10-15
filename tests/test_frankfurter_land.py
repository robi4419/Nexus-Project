from datetime import datetime, timezone

from ingestion.common.landing import LandingVolume
from ingestion.sources.frankfurter.land import land
from tests.fakes import FakeResponse, FakeSession, FakeWorkspaceClient

VOLUME = LandingVolume(catalog="workspace")
RUN_ID = "scheduled__2026-10-01T17:00:00+00:00"
RUN_DATE = datetime(2026, 10, 1, 17, 0, tzinfo=timezone.utc)
FOLDER = "/Volumes/workspace/bronze/landing/frankfurter/ingest_date=2026-10-01/run=scheduled__2026-10-01T17-00-00-00-00"


def test_asks_for_the_run_date_and_writes_the_response_unchanged(frankfurter_rates):
    response = FakeResponse(dict(frankfurter_rates, date="2026-10-01"))
    session = FakeSession([response])
    ws = FakeWorkspaceClient()

    land(session, ws, VOLUME, RUN_ID, RUN_DATE)

    assert session.calls[0]["url"].endswith("/v1/2026-10-01")
    assert ws.files.files == {f"{FOLDER}/rates.json": response.content}


def test_returns_summary(frankfurter_rates):
    holiday_answer = dict(frankfurter_rates, date="2026-09-30")

    summary = land(FakeSession([FakeResponse(holiday_answer)]), FakeWorkspaceClient(), VOLUME, RUN_ID, RUN_DATE)

    assert summary == {
        "source": "frankfurter",
        "folder": FOLDER,
        "requested_date": "2026-10-01",
        "rate_date": "2026-09-30",
        "currencies": sorted(frankfurter_rates["rates"]),
        "removed_files": 0,
    }


def test_rerun_replaces_the_earlier_file(frankfurter_rates):
    ws = FakeWorkspaceClient()
    ws.files.files = {f"{FOLDER}/rates.json": b"old"}
    response = FakeResponse(frankfurter_rates)

    summary = land(FakeSession([response]), ws, VOLUME, RUN_ID, RUN_DATE)

    assert summary["removed_files"] == 1
    assert ws.files.files == {f"{FOLDER}/rates.json": response.content}
