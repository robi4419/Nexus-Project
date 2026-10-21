import pytest
import requests

from ingestion.sources.arbeitnow.client import FEED_URL, PAGE_DELAY, ArbeitnowAPIError, fetch_pages
from tests.fakes import FakeResponse, FakeSession, arbeitnow_body


def fetch_all(session, **options) -> list:
    """Every page, without really waiting between them (unless a test passes its own sleep)."""
    options.setdefault("sleep", lambda seconds: None)
    return list(fetch_pages(session, **options))


def test_asks_for_each_page_until_next_is_empty(arbeitnow_page):
    session = FakeSession([
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=2, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=3, has_next=False)),
    ])

    pages = fetch_all(session)

    assert [page.number for page in pages] == [1, 2, 3]
    assert [call["url"] for call in session.calls] == [FEED_URL] * 3
    assert [call["params"] for call in session.calls] == [{"page": 1}, {"page": 2}, {"page": 3}]


def test_waits_between_pages_but_not_before_the_first(arbeitnow_page):
    session = FakeSession([
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=2, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=3, has_next=False)),
    ])
    waits: list[float] = []

    fetch_all(session, sleep=waits.append)

    assert waits == [PAGE_DELAY, PAGE_DELAY]


def test_a_short_page_is_not_the_last_one(arbeitnow_page):
    one_job = arbeitnow_page["data"][:1]
    session = FakeSession([
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True, jobs=one_job)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=2, has_next=False)),
    ])

    assert len(fetch_all(session)) == 2


def test_page_keeps_raw_bytes_and_parsed_jobs(arbeitnow_page):
    response = FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=False))

    [page] = fetch_all(FakeSession([response]))

    assert page.raw == response.content
    assert [job["slug"] for job in page.jobs] == [job["slug"] for job in arbeitnow_page["data"]]
    assert page.has_next is False


def test_stops_on_empty_page(arbeitnow_page):
    session = FakeSession([FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True, jobs=[]))])

    pages = fetch_all(session)

    assert len(pages) == 1
    assert len(session.calls) == 1


def test_raises_when_the_jobs_list_is_missing(arbeitnow_page):
    body = arbeitnow_body(arbeitnow_page, page=1, has_next=False)
    del body["data"]

    with pytest.raises(ArbeitnowAPIError, match="no list of jobs"):
        fetch_all(FakeSession([FakeResponse(body)]))


def test_raises_when_the_api_answers_with_another_page(arbeitnow_page):
    # e.g. if the API stopped understanding ?page= and returned page 1 every time
    session = FakeSession([
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True)),
        FakeResponse(arbeitnow_body(arbeitnow_page, page=1, has_next=True)),
    ])

    with pytest.raises(ArbeitnowAPIError, match="page 2: the API answered with page 1"):
        fetch_all(session)


def test_raises_after_max_pages(arbeitnow_page):
    session = FakeSession([
        FakeResponse(arbeitnow_body(arbeitnow_page, page=number, has_next=True)) for number in (1, 2, 3)
    ])

    with pytest.raises(ArbeitnowAPIError, match="max_pages=2"):
        fetch_all(session, max_pages=2)
    assert len(session.calls) == 2


def test_http_error_is_raised():
    session = FakeSession([FakeResponse({}, status_code=500)])

    with pytest.raises(requests.HTTPError):
        fetch_all(session)
