"""Write raw API responses to a Unity Catalog Volume.

Layout: /Volumes/<catalog>/<schema>/<volume>/<source>/ingest_date=YYYY-MM-DD/run=<run id>/<file>
"""

import io
import os
import re
from dataclasses import dataclass
from datetime import datetime

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import AlreadyExists, NotFound, ResourceAlreadyExists
from databricks.sdk.service.catalog import VolumeType

DEFAULT_SCHEMA = "bronze"
DEFAULT_VOLUME = "landing"

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class LandingVolume:
    catalog: str
    schema: str = DEFAULT_SCHEMA
    volume: str = DEFAULT_VOLUME

    @classmethod
    def from_env(cls) -> "LandingVolume":
        return cls(
            catalog=os.environ["DATABRICKS_CATALOG"],
            schema=os.environ.get("DATABRICKS_LANDING_SCHEMA") or DEFAULT_SCHEMA,
            volume=os.environ.get("DATABRICKS_LANDING_VOLUME") or DEFAULT_VOLUME,
        )

    @property
    def path(self) -> str:
        return f"/Volumes/{self.catalog}/{self.schema}/{self.volume}"


def ensure_volume(ws: WorkspaceClient, landing: LandingVolume) -> str:
    """Create the schema and the Volume if they don't exist yet; safe to run every time. Returns the Volume path."""
    try:
        ws.schemas.get(f"{landing.catalog}.{landing.schema}")
    except NotFound:
        try:
            ws.schemas.create(
                name=landing.schema,
                catalog_name=landing.catalog,
                comment="Raw data: landed API files and bronze tables",
            )
        except (AlreadyExists, ResourceAlreadyExists):
            pass  # created by another run in the meantime

    try:
        ws.volumes.read(f"{landing.catalog}.{landing.schema}.{landing.volume}")
    except NotFound:
        try:
            ws.volumes.create(
                catalog_name=landing.catalog,
                schema_name=landing.schema,
                name=landing.volume,
                volume_type=VolumeType.MANAGED,
                comment="Raw API responses, one folder per source",
            )
        except (AlreadyExists, ResourceAlreadyExists):
            pass

    return landing.path


def safe_name(value: str) -> str:
    """Make a value usable as a folder name, e.g. 'manual__2026-10-14T10:15:00+00:00' -> 'manual__2026-10-14T10-15-00-00-00'."""
    return _UNSAFE_CHARS.sub("-", value).strip("-")


def run_folder(landing: LandingVolume, source: str, run_id: str, run_date: datetime) -> str:
    """Folder for one pipeline run of one source."""
    return f"{landing.path}/{source}/ingest_date={run_date:%Y-%m-%d}/run={safe_name(run_id)}"


def reset_folder(ws: WorkspaceClient, folder: str) -> int:
    """Delete files left in a run folder by an earlier attempt. Returns how many were removed."""
    try:
        entries = list(ws.files.list_directory_contents(folder))
    except NotFound:
        return 0
    removed = 0
    for entry in entries:
        if not entry.is_directory:
            ws.files.delete(entry.path)
            removed += 1
    return removed


def write_file(ws: WorkspaceClient, path: str, data: bytes) -> None:
    """Upload bytes to a Volume path, replacing any existing file."""
    ws.files.upload(path, io.BytesIO(data), overwrite=True)


def read_file(ws: WorkspaceClient, path: str) -> bytes | None:
    """A Volume file's bytes, or None if there's no such file."""
    try:
        return ws.files.download(path).contents.read()
    except NotFound:
        return None


def list_subfolders(ws: WorkspaceClient, folder: str) -> list[str]:
    """Paths of the folders directly inside a Volume folder, sorted, without the trailing '/'; [] if it doesn't exist."""
    return sorted(entry.path.rstrip("/") for entry in _entries(ws, folder) if entry.is_directory)


def list_files(ws: WorkspaceClient, folder: str) -> list[str]:
    """Paths of the files directly inside a Volume folder, sorted; [] if it doesn't exist."""
    return sorted(entry.path for entry in _entries(ws, folder) if not entry.is_directory)


def _entries(ws: WorkspaceClient, folder: str) -> list:
    try:
        return list(ws.files.list_directory_contents(folder))
    except NotFound:
        return []
