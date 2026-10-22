"""Find which place a raw location string names ("Berlin", "Utrecht, Utrecht, Nederland", "USA", "Remote - EMEA"),
using the reference files locations.csv (hand-made aliases), countries.csv and cities.csv (both from GeoNames).
"""

import csv
import re
from pathlib import Path
from typing import NamedTuple

# Symbols that are never part of a place name, such as emoji flags ("Lyon 🇫🇷"). Letters, digits, spaces, the
# characters used inside names ("'s-Hertogenbosch", "St. Gallen", "Saint-Etienne") and the separators below stay.
_SYMBOLS = re.compile(r"[^\w\s'’.,;|/&:()-]")

# Between the parts of one location: , ; | / & : ( ) and a dash with spaces around it, but not the dash inside
# "Saint-Etienne".
_SEPARATORS = re.compile(r"[,;|/&:()]|\s-\s")

# Words that say how or in which building someone works, not where: "Paris Office", "Munich HQ", "UK - Remote".
_NOISE = re.compile(
    r"\b(?:office|hq|headquarters|hybrid|remote|home ?based|home ?office|warehouse|airport)\b", re.IGNORECASE
)


class Place(NamedTuple):
    location_name: str | None
    location_type: str  # city, country, region, worldwide or unknown
    country_code: str | None
    region: str | None


class Locator:
    """Locates raw location strings. Built from the rows of locations.csv, countries.csv and cities.csv."""

    def __init__(self, aliases: list[dict], countries: list[dict], cities: list[dict]):
        self._regions = {row["country_code"]: row["region"] for row in countries}
        # Lowercased name -> place, for country names and the hand-made aliases. An alias wins over a GeoNames name.
        self._places = {
            row["country_name"].lower(): Place(row["country_name"], "country", row["country_code"], row["region"])
            for row in countries
        }
        for row in aliases:
            self._places[row["raw_value"].lower()] = Place(
                row["location_name"], row["location_type"], row["country_code"] or None, row["region"]
            )
        # Lowercased alias -> (city, country code). cities.csv already keeps one place per alias: a European one, then
        # the most populous.
        self._cities = {row["alias"]: (row["city"], row["country_code"]) for row in cities}

    @classmethod
    def from_csv(cls, reference_dir) -> "Locator":
        def read(name: str) -> list[dict]:
            with open(Path(reference_dir) / name, encoding="utf-8", newline="") as file:
                return list(csv.DictReader(file))

        return cls(read("locations.csv"), read("countries.csv"), read("cities.csv"))

    def _lookup(self, text: str) -> Place | None:
        """The place a whole name stands for: an alias or country first, then a city; None if it's neither."""
        key = text.lower()
        if key in self._places:
            return self._places[key]
        if key in self._cities:
            city, country_code = self._cities[key]
            return Place(city, "city", country_code, self._regions[country_code])
        return None

    def locate(self, raw: str | None) -> Place:
        """The place a raw location string names, as precisely as it can be told:
        1. the whole string as one name ("Berlin", "USA", "Remote job");
        2. otherwise its parts, without noise words ("Paris Office", "UK - Remote", "Utrecht, Utrecht, Nederland"):
           the first city, in the country named if one is (the last one counts); else that country; else the first
           region or worldwide place ("Remote - EMEA");
        3. otherwise unknown, keeping the cleaned text as the name.
        """
        text = " ".join(_SYMBOLS.sub(" ", raw or "").split())
        if not text:
            return Place(None, "unknown", None, None)
        if whole := self._lookup(text):
            return whole

        parts = [" ".join(_NOISE.sub(" ", part).split()) for part in _SEPARATORS.split(text)]
        found = [place for place in map(self._lookup, filter(None, parts)) if place]
        countries = [place for place in found if place.location_type == "country"]
        country_code = countries[-1].country_code if countries else None
        for place in found:
            if place.location_type == "city" and country_code in (None, place.country_code):
                return place
        if countries:
            return countries[-1]
        if found:
            return found[0]
        return Place(text, "unknown", None, None)
