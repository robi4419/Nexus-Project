import json
from datetime import datetime, timezone

from ingestion.common.landing import LandingVolume
from ingestion.sources.himalayas import land as himalayas_land
from ingestion.sources.himalayas.land import land, purge_expired
from tests.fakes import FakeResponse, FakeSession, FakeWorkspaceClient, himalayas_body

VOLUME = LandingVolume(catalog="workspace")
ROOT = "/Volumes/workspace/bronze/landing/himalayas"
NOW = datetime(2026, 10, 21, 18, 0, 5, tzinfo=timezone.utc)
RUN_ID = "scheduled__2026-10-21T18:00:00+00:00"
FOLDER = f"{ROOT}/ingest_date=2026-10-21/run=scheduled__2026-10-21T18-00-00-00-00"
YESTERDAY = f"{ROOT}/ingest_date=2026-10-20/run=scheduled__2026-10-20T18-00-00-00-00"
T = int(NOW.timestamp())  # NOW in Unix seconds
HOUR, DAY = 3600, 86400

# The fixture's jobs, repeated in this order: Tech, Sales, Tech, no parent category. Unless a test says otherwise,
# each job expires 60 days after its pubDate.


def iso(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


def run(session: FakeSession, ws: FakeWorkspaceClient) -> dict:
    return land(session, ws, VOLUME, "test-key", RUN_ID, NOW, now=NOW, delay=0)


def one_page(himalayas_page, *pub_dates: int) -> FakeSession:
    return FakeSession([FakeResponse(himalayas_body(himalayas_page, pub_dates=list(pub_dates)))])


def put_manifest(ws: FakeWorkspaceClient, folder: str, **fields) -> None:
    """A finished earlier run: its manifest, with the fields the next run reads."""
    ws.files.files[f"{folder}/manifest.json"] = json.dumps({"folder": folder, **fields}).encode()


def landed(ws: FakeWorkspaceClient, folder: str = FOLDER) -> dict[str, list[int]]:
    """The pubDates of the jobs in each landed file of a run folder, by file name."""
    return {
        path.rsplit("/", 1)[1]: [job["pubDate"] for job in json.loads(data)["jobs"]]
        for path, data in sorted(ws.files.files.items())
        if path.startswith(f"{folder}/expires_")
    }


# --- land ---------------------------------------------------------------------------------------------------


def test_first_run_goes_back_2_days_and_lands_only_tech_jobs_since_then(himalayas_page):
    page_1 = [T - 1 * HOUR, T - 2 * HOUR, T - 3 * HOUR, T - 4 * HOUR]
    page_2 = [T - 1 * DAY, T - 1 * DAY - 1, T - 3 * DAY, T - 3 * DAY - 1]
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=page_1, cursor="C2")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=page_2, cursor="C3")),
    ])
    ws = FakeWorkspaceClient()

    summary = run(session, ws)

    # Tech jobs only (1st and 3rd of each four), not the one older than 2 days, in one file per expiry day
    assert landed(ws) == {
        "expires_2026-12-19.json": [T - 1 * DAY],
        "expires_2026-12-20.json": [T - 1 * HOUR, T - 3 * HOUR],
    }
    assert summary == {
        "source": "himalayas",
        "folder": FOLDER,
        "cutoff": iso(T - 2 * DAY),
        "cutoff_from": "first run",
        "pages": 2,
        "jobs_seen": 8,
        "tech_jobs": 3,
        "skipped_expiring": 0,
        "files": 2,
        "removed_files": 0,
        "newest_pub_date": iso(T - 1 * HOUR),
        "oldest_pub_date": iso(T - 3 * DAY - 1),
    }
    assert json.loads(ws.files.files[f"{FOLDER}/manifest.json"]) == summary


def test_jobs_expiring_by_tomorrow_are_not_landed(himalayas_page):
    # Tech jobs expiring tomorrow evening and the day after; the purge deletes tomorrow's on the next run anyway
    expiry_dates = [T + DAY, T + DAY, T + 2 * DAY]  # Tech, Sales, Tech
    body = himalayas_body(himalayas_page, pub_dates=[T - HOUR] * 3, expiry_dates=expiry_dates)
    ws = FakeWorkspaceClient()

    summary = run(FakeSession([FakeResponse(body)]), ws)

    assert landed(ws) == {"expires_2026-10-23.json": [T - HOUR]}
    assert (summary["tech_jobs"], summary["skipped_expiring"]) == (1, 1)


def test_the_landed_files_keep_the_jobs_as_the_api_gave_them(himalayas_page):
    body = himalayas_body(himalayas_page, pub_dates=[T - HOUR])
    ws = FakeWorkspaceClient()

    run(FakeSession([FakeResponse(body)]), ws)

    assert json.loads(ws.files.files[f"{FOLDER}/expires_2026-12-20.json"]) == {"jobs": body["jobs"]}


def test_next_run_starts_a_day_before_the_previous_runs_newest_job(himalayas_page):
    ws = FakeWorkspaceClient()
    put_manifest(ws, YESTERDAY, newest_pub_date=iso(T - DAY), cutoff=iso(T - 8 * DAY))

    summary = run(one_page(himalayas_page, T - HOUR, T - 3 * DAY), ws)

    assert (summary["cutoff"], summary["cutoff_from"]) == (iso(T - 2 * DAY), "previous run")


def test_the_newest_finished_run_counts_and_unfinished_runs_are_ignored(himalayas_page):
    ws = FakeWorkspaceClient()
    two_days_ago = f"{ROOT}/ingest_date=2026-10-19/run=scheduled__2026-10-19T18-00-00-00-00"
    yesterday_manual = f"{ROOT}/ingest_date=2026-10-20/run=manual__2026-10-20T09-00-00-00-00"
    today_manual = f"{ROOT}/ingest_date=2026-10-21/run=manual__2026-10-21T09-00-00-00-00"
    put_manifest(ws, two_days_ago, newest_pub_date=iso(T - 2 * DAY))
    put_manifest(ws, YESTERDAY, newest_pub_date=iso(T - DAY))
    put_manifest(ws, yesterday_manual, newest_pub_date=iso(T - 30 * HOUR))
    ws.files.files[f"{today_manual}/expires_2026-12-20.json"] = b'{"jobs": []}'  # failed midway: no manifest

    summary = run(one_page(himalayas_page, T - HOUR, T - 3 * DAY), ws)

    assert summary["cutoff"] == iso(T - 2 * DAY)  # yesterday's scheduled run saw the newest job (T - 1 day)


def test_after_a_long_break_it_catches_up_at_most_7_days(himalayas_page):
    ws = FakeWorkspaceClient()
    put_manifest(ws, YESTERDAY, newest_pub_date=iso(T - 20 * DAY))

    summary = run(one_page(himalayas_page, T - HOUR, T - 8 * DAY), ws)

    assert (summary["cutoff"], summary["cutoff_from"]) == (iso(T - 7 * DAY), "7-day limit")


def test_progress_is_logged_every_log_every_pages(himalayas_page, monkeypatch, caplog):
    monkeypatch.setattr(himalayas_land, "LOG_EVERY", 2)
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[T - n * HOUR], cursor=f"C{n}")) for n in range(1, 4)
    ] + [FakeResponse(himalayas_body(himalayas_page, pub_dates=[T - 3 * DAY]))])

    with caplog.at_level("INFO"):
        run(session, FakeWorkspaceClient())

    assert [record.getMessage() for record in caplog.records if record.getMessage().startswith("page")] == [
        f"page 2: reached {iso(T - 2 * HOUR)} (cutoff {iso(T - 2 * DAY)})",
        f"page 4: reached {iso(T - 3 * DAY)} (cutoff {iso(T - 2 * DAY)})",
    ]


def test_a_cleared_run_fetches_its_own_range_again_and_replaces_its_files(himalayas_page):
    ws = FakeWorkspaceClient()
    put_manifest(ws, YESTERDAY, newest_pub_date=iso(T - HOUR))  # would give a cutoff of T - 25 hours
    put_manifest(ws, FOLDER, newest_pub_date=iso(T - 2 * HOUR), cutoff=iso(T - 5 * DAY))  # this run, finished earlier
    ws.files.files[f"{FOLDER}/expires_2026-12-18.json"] = b"old"
    ws.files.files[f"{FOLDER}/expires_2026-12-19.json"] = b"old"

    summary = run(one_page(himalayas_page, T - HOUR, T - 2 * HOUR, T - 4 * DAY, T - 6 * DAY), ws)

    assert (summary["cutoff"], summary["cutoff_from"]) == (iso(T - 5 * DAY), "earlier attempt of this run")
    assert summary["removed_files"] == 3
    assert landed(ws) == {"expires_2026-12-16.json": [T - 4 * DAY], "expires_2026-12-20.json": [T - HOUR]}


# --- purge_expired -------------------------------------------------------------------------------------------


def test_purge_deletes_job_files_expiring_by_tomorrow_and_keeps_the_rest():
    ws = FakeWorkspaceClient()
    older = f"{ROOT}/ingest_date=2026-08-25/run=scheduled__2026-08-25T18-00-00-00-00"
    for folder, day in [
        (older, "2026-10-20"),  # yesterday
        (older, "2026-10-21"),  # today
        (older, "2026-10-22"),  # tomorrow
        (older, "2026-10-23"),
        (YESTERDAY, "2026-12-19"),
    ]:
        ws.files.files[f"{folder}/expires_{day}.json"] = b'{"jobs": []}'
    put_manifest(ws, older, newest_pub_date=iso(T - 57 * DAY))
    put_manifest(ws, YESTERDAY, newest_pub_date=iso(T - DAY))

    summary = purge_expired(ws, VOLUME, now=NOW)

    assert summary == {"source": "himalayas", "deleted_through": "2026-10-22", "deleted_files": 3, "kept_files": 2}
    assert sorted(ws.files.files) == [
        f"{older}/expires_2026-10-23.json",
        f"{older}/manifest.json",
        f"{YESTERDAY}/expires_2026-12-19.json",
        f"{YESTERDAY}/manifest.json",
    ]


def test_purge_with_nothing_landed_yet():
    assert purge_expired(FakeWorkspaceClient(), VOLUME, now=NOW)["deleted_files"] == 0
