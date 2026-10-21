"""In-memory stand-ins for the HTTP session and the Databricks WorkspaceClient, so tests run offline."""

import copy
import io
import json

import requests
from databricks.sdk.errors import NotFound
from databricks.sdk.service.files import DirectoryEntry, DownloadResponse


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


def himalayas_body(
    template: dict, *, pub_dates: list[int], expiry_dates: list[int] | None = None, cursor: str | None = None
) -> dict:
    """A copy of a Himalayas response with one job per pubDate (the template's jobs, repeated in order) and nextCursor
    replaced; without a cursor, nextCursor is left out, as on the feed's last page. Each job expires 60 days after its
    pubDate, as almost all real ones do, unless expiry_dates are given."""
    body = copy.deepcopy(template)
    jobs = template["jobs"]
    expiry_dates = expiry_dates or [value + 60 * 86400 for value in pub_dates]
    body["jobs"] = [
        {**copy.deepcopy(jobs[i % len(jobs)]), "pubDate": pub_date, "expiryDate": expiry_date}
        for i, (pub_date, expiry_date) in enumerate(zip(pub_dates, expiry_dates, strict=True))
    ]
    body.pop("nextCursor", None)
    if cursor:
        body["nextCursor"] = cursor
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

    def get(self, url: str, params: dict | None = None, headers: dict | None = None) -> FakeResponse:
        call = {"url": url, "params": dict(params or {})}
        if headers is not None:
            call["headers"] = dict(headers)
        self.calls.append(call)
        return self.responses.pop(0)


class FakeFiles:
    """Volume files kept in a dict: path -> bytes. Folders exist only through the files inside them."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def list_directory_contents(self, directory_path: str) -> list[DirectoryEntry]:
        """What's directly inside a folder: its files, and its subfolders with a trailing '/' as the real API gives."""
        prefix = directory_path.rstrip("/") + "/"
        entries: dict[str, DirectoryEntry] = {}
        for path in self.files:
            if not path.startswith(prefix):
                continue
            name, _, rest = path[len(prefix):].partition("/")
            if rest:
                entries[name] = DirectoryEntry(path=f"{prefix}{name}/", name=name, is_directory=True)
            else:
                entries[name] = DirectoryEntry(path=path, name=name, is_directory=False)
        if not entries:
            raise NotFound(f"directory not found: {directory_path}")
        return list(entries.values())

    def delete(self, file_path: str) -> None:
        del self.files[file_path]

    def upload(self, file_path: str, contents, *, overwrite: bool | None = None) -> None:
        self.files[file_path] = contents.read()

    def download(self, file_path: str) -> DownloadResponse:
        if file_path not in self.files:
            raise NotFound(f"file not found: {file_path}")
        return DownloadResponse(contents=io.BytesIO(self.files[file_path]))


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
