"""Arbeitnow API client: walks the job board feed (a rolling window of about 7 days) page by page.

Docs: https://www.arbeitnow.com/blog/job-board-api
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import requests

SOURCE = "arbeitnow"
FEED_URL = "https://www.arbeitnow.com/api/job-board-api"
MAX_PAGES = 60  # safety cap; the whole feed is about 28 pages of up to 300 jobs
PAGE_DELAY = 2.0  # seconds between requests: the API is free and asks not to be abused


class ArbeitnowAPIError(RuntimeError):
    """The API answered but returned something unexpected."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    raw: bytes  # response body exactly as received, to be landed untouched
    jobs: list[dict]
    has_next: bool


def fetch_pages(
    session: requests.Session,
    max_pages: int = MAX_PAGES,
    delay: float = PAGE_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[Page]:
    """Yield every page of the feed, asking for ?page=1, 2, 3… until links.next is empty.

    Pages get shorter towards the end (300, 281, 150…), so a short page doesn't mean the last one.
    """
    for number in range(1, max_pages + 1):
        if number > 1:
            sleep(delay)
        response = session.get(FEED_URL, params={"page": number})
        response.raise_for_status()
        body = response.json()

        jobs = body.get("data")
        if not isinstance(jobs, list):
            raise ArbeitnowAPIError(f"page {number}: the response has no list of jobs")
        current_page = (body.get("meta") or {}).get("current_page")
        if current_page != number:
            raise ArbeitnowAPIError(f"page {number}: the API answered with page {current_page!r}")

        page = Page(number=number, raw=response.content, jobs=jobs, has_next=bool((body.get("links") or {}).get("next")))
        yield page

        if not jobs or not page.has_next:
            return

    raise ArbeitnowAPIError(f"feed still has more pages after max_pages={max_pages}")
