from datetime import datetime, timezone

from ingestion.common.landing import LandingVolume
from ingestion.sources.arbeitnow.land import land
from tests.fakes import FakeResponse, FakeSession, FakeWorkspaceClient, arbeitnow_body

VOLUME = LandingVolume(catalog="workspace")
RUN_ID = "manual__2026-10-21T18:00:00+00:00"
RUN_DATE = datetime(2026, 10, 21, 18, 0, tzinfo=timezone.utc)
FOLDER = "/Volumes/workspace/bronze/landing/arbeitnow/ingest_date=2026-10-21/run=manual__2026-10-21T18-00-00-00-00"


def two_pages(arbeitnow_page) -> list[FakeResponse]:
    return [
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=2, has_next=False)),
    ]


def test_writes_each_page_unchanged_to_its_own_file(arbeitnow_page):
    responses = two_pages(arbeitnow_page)
    ws = FakeWorkspaceClient()

    land(FakeSession(responses), ws, VOLUME, RUN_ID, RUN_DATE, delay=0)

    assert ws.files.files == {
        f"{FOLDER}/page_001.json": responses[0].content,
        f"{FOLDER}/page_002.json": responses[1].content,
    }


def test_returns_summary(arbeitnow_page):
    created = sorted(job["created_at"] for job in arbeitnow_page["data"])

    summary = land(FakeSession(two_pages(arbeitnow_page)), FakeWorkspaceClient(), VOLUME, RUN_ID, RUN_DATE, delay=0)

    assert summary == {
        "source": "arbeitnow",
        "folder": FOLDER,
        "pages": 2,
        "jobs": 4,  # both pages hold the same two jobs...
        "distinct_jobs": 2,  # ...so each is counted once here
        "remote_jobs": 2,  # one remote job per page
        "removed_files": 0,
        "oldest_created_at": datetime.fromtimestamp(created[0], tz=timezone.utc).isoformat(),
        "newest_created_at": datetime.fromtimestamp(created[-1], tz=timezone.utc).isoformat(),
    }


def test_rerun_replaces_files_from_an_earlier_attempt(arbeitnow_page):
    ws = FakeWorkspaceClient()
    ws.files.files = {
        f"{FOLDER}/page_001.json": b"old",
        f"{FOLDER}/page_002.json": b"old",
        f"{FOLDER}/page_003.json": b"old",
    }
    response = FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=False))

    summary = land(FakeSession([response]), ws, VOLUME, RUN_ID, RUN_DATE, delay=0)

    assert summary["removed_files"] == 3
    assert ws.files.files == {f"{FOLDER}/page_001.json": response.content}
