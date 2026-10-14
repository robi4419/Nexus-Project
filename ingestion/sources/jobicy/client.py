"""Jobicy API client: walks the remote jobs feed (last 7 days) page by page.

Docs: https://github.com/Jobicy/remote-jobs-api
"""

from collections.abc import Iterator
from dataclasses import dataclass

import requests

SOURCE = "jobicy"
FEED_URL = "https://jobicy.com/api/v2/remote-jobs"
PAGE_SIZE = 200  # API maximum
MAX_PAGES = 20  # safety cap; the whole feed is ~4 pages


class JobicyAPIError(RuntimeError):
    """The API answered but reported a failure or returned something unexpected."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    raw: bytes  # response body exactly as received, to be landed untouched
    jobs: list[dict]
    has_more: bool
    next_cursor: str | None


def fetch_pages(
    session: requests.Session,
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> Iterator[Page]:
    """Yield every page of the feed, newest jobs first, following nextCursor until hasMore is false."""
    params = {"count": page_size}
    for number in range(1, max_pages + 1):
        response = session.get(FEED_URL, params=params)
        response.raise_for_status()
        body = response.json()
        if not body.get("success", False):
            raise JobicyAPIError(f"page {number}: API reported failure (statusCode={body.get('statusCode')})")

        jobs = body.get("jobs") or []
        page = Page(
            number=number,
            raw=response.content,
            jobs=jobs,
            has_more=bool(body.get("hasMore")),
            next_cursor=body.get("nextCursor"),
        )
        yield page

        if not jobs or not page.has_more:
            return
        if not page.next_cursor:
            raise JobicyAPIError(f"page {number}: hasMore is true but nextCursor is missing")
        params = {"count": page_size, "cursor": page.next_cursor}

    raise JobicyAPIError(f"feed still has more pages after max_pages={max_pages}")
