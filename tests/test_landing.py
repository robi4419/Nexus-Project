from datetime import datetime, timezone

from ingestion.common.landing import (
    LandingVolume,
    ensure_volume,
    reset_folder,
    run_folder,
    safe_name,
    write_file,
)
from tests.fakes import FakeWorkspaceClient

VOLUME = LandingVolume(catalog="workspace")


def test_volume_path_uses_defaults():
    assert VOLUME.path == "/Volumes/workspace/bronze/landing"


def test_from_env_reads_catalog_and_overrides(monkeypatch):
    monkeypatch.setenv("DATABRICKS_CATALOG", "dev")
    monkeypatch.setenv("DATABRICKS_LANDING_SCHEMA", "raw")
    monkeypatch.delenv("DATABRICKS_LANDING_VOLUME", raising=False)

    assert LandingVolume.from_env() == LandingVolume(catalog="dev", schema="raw", volume="landing")


def test_from_env_treats_empty_values_as_defaults(monkeypatch):
    monkeypatch.setenv("DATABRICKS_CATALOG", "workspace")
    monkeypatch.setenv("DATABRICKS_LANDING_SCHEMA", "")
    monkeypatch.setenv("DATABRICKS_LANDING_VOLUME", "")

    assert LandingVolume.from_env() == VOLUME


def test_ensure_volume_creates_missing_schema_and_volume():
    ws = FakeWorkspaceClient()

    assert ensure_volume(ws, VOLUME) == "/Volumes/workspace/bronze/landing"
    assert ws.schemas.created == ["workspace.bronze"]
    assert ws.volumes.created == ["workspace.bronze.landing"]


def test_ensure_volume_leaves_existing_ones_alone():
    ws = FakeWorkspaceClient(schemas=["workspace.bronze"], volumes=["workspace.bronze.landing"])

    ensure_volume(ws, VOLUME)

    assert ws.schemas.created == []
    assert ws.volumes.created == []


def test_safe_name_replaces_characters_unsafe_in_paths():
    assert safe_name("manual__2026-10-14T10:15:00+00:00") == "manual__2026-10-14T10-15-00-00-00"


def test_run_folder_layout():
    run_date = datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc)

    folder = run_folder(VOLUME, "jobicy", "scheduled__2026-10-14T18:00:00+00:00", run_date)

    assert folder == (
        "/Volumes/workspace/bronze/landing/jobicy/"
        "ingest_date=2026-10-14/run=scheduled__2026-10-14T18-00-00-00-00"
    )


def test_reset_folder_deletes_only_files_in_that_folder():
    ws = FakeWorkspaceClient()
    ws.files.files = {
        "/v/jobicy/run=1/page_001.json": b"a",
        "/v/jobicy/run=1/page_002.json": b"b",
        "/v/jobicy/run=10/page_001.json": b"c",
    }

    assert reset_folder(ws, "/v/jobicy/run=1") == 2
    assert list(ws.files.files) == ["/v/jobicy/run=10/page_001.json"]


def test_reset_folder_on_missing_folder_does_nothing():
    assert reset_folder(FakeWorkspaceClient(), "/v/jobicy/run=1") == 0


def test_write_file_uploads_bytes():
    ws = FakeWorkspaceClient()

    write_file(ws, "/v/jobicy/page_001.json", b'{"jobs": []}')

    assert ws.files.files == {"/v/jobicy/page_001.json": b'{"jobs": []}'}
