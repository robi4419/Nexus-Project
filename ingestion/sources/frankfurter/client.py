"""Frankfurter API client: the European Central Bank's daily reference exchange rates.

Docs: https://frankfurter.dev
"""

from dataclasses import dataclass
from datetime import date

import requests

SOURCE = "frankfurter"
RATES_URL = "https://api.frankfurter.dev/v1/{on_date}"
BASE_CURRENCY = "USD"


class FrankfurterAPIError(RuntimeError):
    """The API answered but returned something unexpected."""


@dataclass(frozen=True)
class Rates:
    raw: bytes  # response body exactly as received, to be landed untouched
    rate_date: date  # ECB publication date; earlier than requested on weekends and holidays
    rates: dict[str, float]  # units of each currency per 1 unit of the base currency


def fetch_rates(session: requests.Session, on_date: date, base: str = BASE_CURRENCY) -> Rates:
    """Fetch the rates published on `on_date`, or on the last working day before it."""
    response = session.get(RATES_URL.format(on_date=on_date.isoformat()), params={"base": base})
    response.raise_for_status()
    body = response.json()

    if body.get("base") != base:
        raise FrankfurterAPIError(f"asked for base {base}, got {body.get('base')!r}")
    if not body.get("date"):
        raise FrankfurterAPIError(f"response for {on_date} has no date")
    rates = body.get("rates") or {}
    if not rates:
        raise FrankfurterAPIError(f"no rates returned for {on_date}")

    return Rates(raw=response.content, rate_date=date.fromisoformat(body["date"]), rates=rates)
