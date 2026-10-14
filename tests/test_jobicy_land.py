from datetime import datetime, timezone

from ingestion.common.landing import LandingVolume
from ingestion.sources.jobicy.land import land
from tests.fakes import FakeResponse, FakeSession, FakeWorkspaceClient, jobicy_body

VOLUME = LandingVolume(catalog="workspace")
RUN_ID = "manual__2026-10-14T10:15:00+00:00"
RUN_DATE = datetime(2026, 10, 14, 10, 15, tzinfo=timezone.utc)
FOLDER = "/Volumes/workspace/bronze/landing/jobicy/ingest_date=2026-10-14/run=manual__2026-10-14T10-15-00-00-00"


def two_pages(jobicy_page) -> list[FakeResponse]:
    return [
        FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor="C2")),
        FakeResponse(jobicy_body(jobicy_page, has_more=False)),
    ]


def test_writes_each_page_unchanged_to_its_own_file(jobicy_page):
    responses = two_pages(jobicy_page)
    ws = FakeWorkspaceClient()

    land(FakeSession(responses), ws, VOLUME, RUN_ID, RUN_DATE)

    assert ws.files.files == {
        f"{FOLDER}/page_001.json": responses[0].content,
        f"{FOLDER}/page_002.json": responses[1].content,
    }


def test_returns_summary(jobicy_page):
    pub_dates = sorted(job["pubDate"] for job in jobicy_page["jobs"])

    summary = land(FakeSession(two_pages(jobicy_page)), FakeWorkspaceClient(), VOLUME, RUN_ID, RUN_DATE)

    assert summary == {
        "source": "jobicy",
        "folder": FOLDER,
        "pages": 2,
        "jobs": 2 * len(jobicy_page["jobs"]),
        "removed_files": 0,
        "oldest_pub_date": pub_dates[0],
        "newest_pub_date": pub_dates[-1],
    }


def test_rerun_replaces_files_from_an_earlier_attempt(jobicy_page):
    ws = FakeWorkspaceClient()
    ws.files.files = {
        f"{FOLDER}/page_001.json": b"old",
        f"{FOLDER}/page_002.json": b"old",
        f"{FOLDER}/page_003.json": b"old",
    }
    response = FakeResponse(jobicy_body(jobicy_page, has_more=False))

    summary = land(FakeSession([response]), ws, VOLUME, RUN_ID, RUN_DATE)

    assert summary["removed_files"] == 3
    assert ws.files.files == {f"{FOLDER}/page_001.json": response.content}
