import pytest
import requests

from ingestion.sources.himalayas.client import FEED_URL, REQUEST_DELAY, HimalayasAPIError, fetch_pages
from tests.fakes import FakeResponse, FakeSession, himalayas_body


def fetch_all(session, stop_before: int = 0, **options) -> list:
    """Every page down to stop_before, without really waiting between them (unless a test passes its own sleep)."""
    options.setdefault("sleep", lambda seconds: None)
    return list(fetch_pages(session, "test-key", stop_before, **options))


def test_sends_the_key_as_a_bearer_header_and_follows_the_cursor(himalayas_page):
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[500, 400], cursor="C2")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[300, 200])),
    ])

    pages = fetch_all(session)

    assert [page.number for page in pages] == [1, 2]
    assert [call["url"] for call in session.calls] == [FEED_URL] * 2
    assert [call["params"] for call in session.calls] == [{"limit": 20}, {"limit": 20, "cursor": "C2"}]
    assert [call["headers"] for call in session.calls] == [{"Authorization": "Bearer test-key"}] * 2


def test_stops_at_the_page_that_reaches_the_cutoff(himalayas_page):
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[500, 400], cursor="C2")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[300, 200], cursor="C3")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[100, 50], cursor="C4")),
    ])

    pages = fetch_all(session, stop_before=250)

    assert [page.oldest_pub_date for page in pages] == [400, 200]  # 200 is older than 250, so page 2 is the last
    assert len(session.calls) == 2


def test_a_page_ending_exactly_at_the_cutoff_is_not_the_last(himalayas_page):
    # More jobs from the same second may follow on the next page, and jobs at the cutoff are kept.
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[500, 400], cursor="C2")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[400, 300])),
    ])

    assert len(fetch_all(session, stop_before=400)) == 2


def test_stops_when_the_feed_ends(himalayas_page):
    session = FakeSession([FakeResponse(himalayas_body(himalayas_page, pub_dates=[500, 400]))])

    assert len(fetch_all(session, stop_before=100)) == 1


def test_stops_on_empty_page(himalayas_page):
    session = FakeSession([FakeResponse(himalayas_body(himalayas_page, pub_dates=[], cursor="C2"))])

    [page] = fetch_all(session)

    assert page.jobs == [] and page.oldest_pub_date is None
    assert len(session.calls) == 1


def test_waits_between_requests_but_not_before_the_first(himalayas_page):
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[500], cursor="C2")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[400], cursor="C3")),
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[300])),
    ])
    waits: list[float] = []

    fetch_all(session, sleep=waits.append)

    assert waits == [REQUEST_DELAY, REQUEST_DELAY]


def test_raises_when_the_jobs_list_is_missing(himalayas_page):
    body = himalayas_body(himalayas_page, pub_dates=[500])
    del body["jobs"]

    with pytest.raises(HimalayasAPIError, match="no list of jobs"):
        fetch_all(FakeSession([FakeResponse(body)]))


@pytest.mark.parametrize("field", ["pubDate", "expiryDate"])
def test_raises_when_a_job_has_no_pub_date_or_expiry_date(himalayas_page, field):
    body = himalayas_body(himalayas_page, pub_dates=[500, 400])
    del body["jobs"][1][field]

    with pytest.raises(HimalayasAPIError, match="no pubDate or expiryDate"):
        fetch_all(FakeSession([FakeResponse(body)]))


@pytest.mark.parametrize(
    ("pub_date", "expiry_date"),
    [(1792509727000, 1797693727), (1792509727, 1797693727000)],
)
def test_raises_when_a_date_looks_like_milliseconds(himalayas_page, pub_date, expiry_date):
    body = himalayas_body(himalayas_page, pub_dates=[pub_date], expiry_dates=[expiry_date], cursor="C2")

    with pytest.raises(HimalayasAPIError, match="milliseconds"):
        fetch_all(FakeSession([FakeResponse(body)]))


def test_raises_after_max_pages(himalayas_page):
    session = FakeSession([
        FakeResponse(himalayas_body(himalayas_page, pub_dates=[500 - n], cursor=f"C{n}")) for n in range(3)
    ])

    with pytest.raises(HimalayasAPIError, match="max_pages=2"):
        fetch_all(session, max_pages=2)
    assert len(session.calls) == 2


def test_http_error_is_raised():
    session = FakeSession([FakeResponse({}, status_code=401)])  # e.g. a wrong key

    with pytest.raises(requests.HTTPError):
        fetch_all(session)
