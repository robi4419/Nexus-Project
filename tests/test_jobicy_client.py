import pytest
import requests

from ingestion.sources.jobicy.client import FEED_URL, JobicyAPIError, fetch_pages
from tests.fakes import FakeResponse, FakeSession, jobicy_body


def test_follows_cursor_until_has_more_is_false(jobicy_page):
    session = FakeSession([
        FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor="C2")),
        FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor="C3")),
        FakeResponse(jobicy_body(jobicy_page, has_more=False)),
    ])

    pages = list(fetch_pages(session))

    assert [page.number for page in pages] == [1, 2, 3]
    assert [call["url"] for call in session.calls] == [FEED_URL] * 3
    assert [call["params"] for call in session.calls] == [
        {"count": 200},
        {"count": 200, "cursor": "C2"},
        {"count": 200, "cursor": "C3"},
    ]


def test_page_size_is_sent_as_count(jobicy_page):
    session = FakeSession([FakeResponse(jobicy_body(jobicy_page, has_more=False))])

    list(fetch_pages(session, page_size=50))

    assert session.calls[0]["params"] == {"count": 50}


def test_page_keeps_raw_bytes_and_parsed_jobs(jobicy_page):
    response = FakeResponse(jobicy_body(jobicy_page, has_more=False))

    [page] = fetch_pages(FakeSession([response]))

    assert page.raw == response.content
    assert [job["id"] for job in page.jobs] == [job["id"] for job in jobicy_page["jobs"]]
    assert page.has_more is False


def test_stops_on_empty_page(jobicy_page):
    session = FakeSession([FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor="C2", jobs=[]))])

    pages = list(fetch_pages(session))

    assert len(pages) == 1
    assert len(session.calls) == 1


def test_raises_when_api_reports_failure(jobicy_page):
    body = jobicy_body(jobicy_page, has_more=False)
    body["success"] = False

    with pytest.raises(JobicyAPIError, match="API reported failure"):
        list(fetch_pages(FakeSession([FakeResponse(body)])))


def test_raises_when_has_more_but_no_cursor(jobicy_page):
    session = FakeSession([FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor=None))])

    with pytest.raises(JobicyAPIError, match="nextCursor is missing"):
        list(fetch_pages(session))


def test_raises_after_max_pages(jobicy_page):
    session = FakeSession([
        FakeResponse(jobicy_body(jobicy_page, has_more=True, cursor=f"C{i}")) for i in range(3)
    ])

    with pytest.raises(JobicyAPIError, match="max_pages=2"):
        list(fetch_pages(session, max_pages=2))
    assert len(session.calls) == 2


def test_http_error_is_raised():
    session = FakeSession([FakeResponse({}, status_code=500)])

    with pytest.raises(requests.HTTPError):
        list(fetch_pages(session))
