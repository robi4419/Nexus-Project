from datetime import date

import pytest
import requests

from ingestion.sources.frankfurter.client import FrankfurterAPIError, fetch_rates
from tests.fakes import FakeResponse, FakeSession


def test_requests_the_date_in_the_path_with_usd_base(frankfurter_rates):
    session = FakeSession([FakeResponse(frankfurter_rates)])

    fetch_rates(session, date(2026, 10, 14))

    assert session.calls == [{"url": "https://api.frankfurter.dev/v1/2026-10-14", "params": {"base": "USD"}}]


def test_returns_raw_bytes_rate_date_and_rates(frankfurter_rates):
    response = FakeResponse(frankfurter_rates)

    rates = fetch_rates(FakeSession([response]), date(2026, 10, 14))

    assert rates.raw == response.content
    assert rates.rate_date == date(2026, 10, 14)
    assert rates.rates["EUR"] == 0.89326


def test_rate_date_can_be_earlier_than_requested(frankfurter_rates):
    saturday_answer = dict(frankfurter_rates, date="2026-10-09")

    rates = fetch_rates(FakeSession([FakeResponse(saturday_answer)]), date(2026, 10, 10))

    assert rates.rate_date == date(2026, 10, 9)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"base": "EUR"}, "asked for base USD"),
        ({"date": None}, "has no date"),
        ({"rates": {}}, "no rates returned"),
    ],
)
def test_raises_on_unexpected_response(frankfurter_rates, change, message):
    body = dict(frankfurter_rates, **change)

    with pytest.raises(FrankfurterAPIError, match=message):
        fetch_rates(FakeSession([FakeResponse(body)]), date(2026, 10, 14))


def test_http_error_is_raised():
    session = FakeSession([FakeResponse({}, status_code=503)])

    with pytest.raises(requests.HTTPError):
        fetch_rates(session, date(2026, 10, 14))
