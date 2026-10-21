"""Himalayas API client: walks the remote jobs feed, most recently updated first, back to a cutoff.

Docs: https://himalayas.app/docs/remote-jobs-api
"""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

import requests

SOURCE = "himalayas"
FEED_URL = "https://himalayas.app/jobs/api"
PAGE_SIZE = 20  # API maximum
REQUEST_DELAY = 1.0  # seconds between requests: an API key allows 60 a minute
MAX_PAGES = 2000  # safety cap; a normal day is about 330 pages, catching up the maximum 7 days about 1,200


class HimalayasAPIError(RuntimeError):
    """The API answered but returned something unexpected."""


@dataclass(frozen=True)
class Page:
    number: int  # 1-based
    jobs: list[dict]
    oldest_pub_date: int | None  # Unix seconds; None for an empty page


def fetch_pages(
    session: requests.Session,
    api_key: str,
    stop_before: int,
    max_pages: int = MAX_PAGES,
    delay: float = REQUEST_DELAY,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[Page]:
    """Yield pages newest first, following nextCursor, until a page reaches a job last updated before `stop_before`
    (Unix seconds) or the feed ends. That last page can also hold older jobs; the caller leaves them out.

    The key goes in the Authorization header, never in the URL, so it can't end up in logs or error messages.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"limit": PAGE_SIZE}
    for number in range(1, max_pages + 1):
        if number > 1:
            sleep(delay)
        response = session.get(FEED_URL, params=params, headers=headers)
        response.raise_for_status()
        body = response.json()

        jobs = body.get("jobs")
        if not isinstance(jobs, list):
            raise HimalayasAPIError(f"page {number}: the response has no list of jobs")
        # pubDate decides where the walk stops, expiryDate when a landed job must be deleted: both are required.
        pub_dates = [job.get("pubDate") for job in jobs]
        dates = pub_dates + [job.get("expiryDate") for job in jobs]
        if not all(isinstance(value, (int, float)) for value in dates):
            raise HimalayasAPIError(f"page {number}: a job has no pubDate or expiryDate")
        # The docs once described dates in milliseconds; real responses use seconds. Milliseconds would never reach
        # the cutoff, so fail instead of walking the whole feed.
        if any(value > 10**11 for value in dates):
            raise HimalayasAPIError(f"page {number}: a date looks like milliseconds, not seconds")

        page = Page(number=number, jobs=jobs, oldest_pub_date=min(pub_dates, default=None))
        yield page

        next_cursor = body.get("nextCursor")
        if not jobs or not next_cursor or page.oldest_pub_date < stop_before:
            return
        params = {"limit": PAGE_SIZE, "cursor": next_cursor}

    raise HimalayasAPIError(f"the feed is still newer than the cutoff after max_pages={max_pages}")
