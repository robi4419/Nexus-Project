"""In-memory stand-ins for the HTTP session and the Databricks WorkspaceClient, so tests run offline."""

import copy
import json

import requests
from databricks.sdk.errors import NotFound
from databricks.sdk.service.files import DirectoryEntry


def jobicy_body(template: dict, *, has_more: bool, cursor: str | None = None, jobs: list | None = None) -> dict:
    """A copy of a Jobicy response with the paging fields (and optionally the jobs) replaced."""
    body = copy.deepcopy(template)
    body["hasMore"] = has_more
    body["nextCursor"] = cursor
    if jobs is not None:
        body["jobs"] = jobs
    return body


def arbeitnow_body(template: dict, *, page: int, has_next: bool, jobs: list | None = None) -> dict:
    """A copy of an Arbeitnow response for another page number, with links.next (and optionally the jobs) replaced."""
    body = copy.deepcopy(template)
    body["meta"]["current_page"] = page
    body["links"]["next"] = f"https://www.arbeitnow.com/api/job-board-api?page={page + 1}" if has_next else None
    if jobs is not None:
        body["data"] = jobs
    return body


class FakeResponse:
    """Looks like requests.Response for the parts our code uses."""

    def __init__(self, body: dict, status_code: int = 200):
        self.content = json.dumps(body).encode("utf-8")
        self.status_code = status_code

    def json(self) -> dict:
        return json.loads(self.content)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


class FakeSession:
    """Returns prepared responses in order and records every call."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url: str, params: dict | None = None) -> FakeResponse:
        self.calls.append({"url": url, "params": dict(params or {})})
        return self.responses.pop(0)


class FakeFiles:
    """Volume files kept in a dict: path -> bytes."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def list_directory_contents(self, directory_path: str) -> list[DirectoryEntry]:
        prefix = directory_path.rstrip("/") + "/"
        paths = [path for path in self.files if path.startswith(prefix)]
        if not paths:
            raise NotFound(f"directory not found: {directory_path}")
        return [DirectoryEntry(path=path, is_directory=False) for path in paths]

    def delete(self, file_path: str) -> None:
        del self.files[file_path]

    def upload(self, file_path: str, contents, *, overwrite: bool | None = None) -> None:
        self.files[file_path] = contents.read()


class FakeSchemas:
    def __init__(self, existing: list[str]):
        self.existing = set(existing)  # full names, e.g. "workspace.bronze"
        self.created: list[str] = []

    def get(self, full_name: str) -> None:
        if full_name not in self.existing:
            raise NotFound(f"schema not found: {full_name}")

    def create(self, name: str, catalog_name: str, **kwargs) -> None:
        full_name = f"{catalog_name}.{name}"
        self.existing.add(full_name)
        self.created.append(full_name)


class FakeVolumes:
    def __init__(self, existing: list[str]):
        self.existing = set(existing)  # full names, e.g. "workspace.bronze.landing"
        self.created: list[str] = []

    def read(self, name: str) -> None:
        if name not in self.existing:
            raise NotFound(f"volume not found: {name}")

    def create(self, catalog_name: str, schema_name: str, name: str, volume_type, **kwargs) -> None:
        full_name = f"{catalog_name}.{schema_name}.{name}"
        self.existing.add(full_name)
        self.created.append(full_name)


class FakeWorkspaceClient:
    """Has the same .files, .schemas and .volumes attributes our code uses on a real WorkspaceClient."""

    def __init__(self, schemas: list[str] = (), volumes: list[str] = ()):
        self.files = FakeFiles()
        self.schemas = FakeSchemas(schemas)
        self.volumes = FakeVolumes(volumes)
