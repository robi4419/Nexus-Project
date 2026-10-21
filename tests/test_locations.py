import csv
import io
import json
from pathlib import Path

import pytest

from transform.locations import Locator, Place

REFERENCE_DIR = Path(__file__).parent.parent / "databricks" / "reference"
VOCABULARY = Path(__file__).parent / "fixtures" / "source_vocabulary.json"


def rows(text: str) -> list[dict]:
    """The rows of a small CSV written in the test, read the way Locator.from_csv reads the real files."""
    return list(csv.DictReader(io.StringIO(text.strip())))


# A small hand-made reference, so each rule can be tested with nothing else in the way.
ALIASES = rows("""
raw_value,location_name,location_type,country_code,region
USA,United States,country,US,North America
Nederland,Netherlands,country,NL,Europe
Remote,Anywhere,worldwide,,Worldwide
EMEA,EMEA,region,,EMEA
""")
COUNTRIES = rows("""
country_code,country_name,region
CA,Canada,North America
GB,United Kingdom,Europe
NL,Netherlands,Europe
US,United States,North America
""")
CITIES = rows("""
alias,city,country_code,population
london,London,GB,8961989
utrecht,Utrecht,NL,290529
den haag,The Hague,NL,474292
""")

UNITED_STATES = Place("United States", "country", "US", "North America")
NETHERLANDS = Place("Netherlands", "country", "NL", "Europe")
CANADA = Place("Canada", "country", "CA", "North America")
ANYWHERE = Place("Anywhere", "worldwide", None, "Worldwide")
EMEA = Place("EMEA", "region", None, "EMEA")
LONDON = Place("London", "city", "GB", "Europe")
UTRECHT = Place("Utrecht", "city", "NL", "Europe")
NOTHING = Place(None, "unknown", None, None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # 1. the whole string is one name: an alias, a country or a city, ignoring case and extra spaces
        ("USA", UNITED_STATES),
        ("usa", UNITED_STATES),
        ("Nederland", NETHERLANDS),
        ("Netherlands", NETHERLANDS),
        ("Remote", ANYWHERE),
        ("EMEA", EMEA),
        ("Utrecht", UTRECHT),
        ("  den   HAAG ", Place("The Hague", "city", "NL", "Europe")),
        ("Utrecht 🇳🇱", UTRECHT),  # symbols such as emoji flags are dropped
        # 2. the parts: the first city, in the country named if there is one
        ("Utrecht, Utrecht, Nederland", UTRECHT),
        ("Netherlands - Utrecht - Hybrid", UTRECHT),
        ("London; Utrecht", LONDON),
        ("Den Haag/Utrecht", Place("The Hague", "city", "NL", "Europe")),
        ("UK: London (Moorgate)", LONDON),
        ("Utrecht Office", UTRECHT),  # noise words are dropped from each part
        ("London HQ", LONDON),
        ("Hybrid London", LONDON),
        ("Utrecht & Remote", UTRECHT),
        ("London, Ontario, Canada", CANADA),  # this London isn't in Canada: only the country is known
        ("Woerden, Utrecht, Nederland", UTRECHT),  # a region named like its main city counts as that city
        ("Marknesse, Flevoland, Nederland", NETHERLANDS),  # no known city: the country
        ("Netherlands - Remote", NETHERLANDS),
        ("Home Office (Netherlands)", NETHERLANDS),
        ("Homebased - USA", UNITED_STATES),
        ("Remote - EMEA", EMEA),  # no city or country: the first region
        # 3. unknown, keeping the cleaned text as the name
        ("Hybrid", Place("Hybrid", "unknown", None, None)),
        ("Portfolio   Location", Place("Portfolio Location", "unknown", None, None)),
        ("Saint-Utrecht", Place("Saint-Utrecht", "unknown", None, None)),  # a dash inside a name doesn't split it
        ("", NOTHING),
        ("   ", NOTHING),
        ("🇪🇺", NOTHING),
        (None, NOTHING),
    ],
)
def test_rules(raw, expected):
    assert Locator(ALIASES, COUNTRIES, CITIES).locate(raw) == expected


def test_an_alias_wins_over_a_country_name():
    aliases = rows("""
raw_value,location_name,location_type,country_code,region
Netherlands,Holland,country,NL,Europe
""")

    assert Locator(aliases, COUNTRIES, CITIES).locate("Netherlands") == Place("Holland", "country", "NL", "Europe")


# --- the real reference files -------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def locator() -> Locator:
    return Locator.from_csv(REFERENCE_DIR)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # real Arbeitnow values (2026-10-20)
        ("Berlin", ("Berlin", "city", "DE", "Europe")),
        ("Zurich, Zürich, Switzerland", ("Zürich", "city", "CH", "Europe")),
        ("Utrecht, Utrecht, Nederland", ("Utrecht", "city", "NL", "Europe")),
        ("Den Haag, Zuid-Holland, Netherlands", ("The Hague", "city", "NL", "Europe")),
        ("GRENOBLE , Auvergne-Rhône-Alpes, France", ("Grenoble", "city", "FR", "Europe")),
        ("Cologne", ("Köln", "city", "DE", "Europe")),
        ("Munich HQ", ("Munich", "city", "DE", "Europe")),
        ("Paris Office", ("Paris", "city", "FR", "Europe")),
        ("Lyon 🇫🇷", ("Lyon", "city", "FR", "Europe")),
        ("UK: London (7 Devonshire Square)", ("London", "city", "GB", "Europe")),
        ("Germany - Regensburg - Hybrid", ("Regensburg", "city", "DE", "Europe")),
        ("Lausanne / Hybrid / Remote", ("Lausanne", "city", "CH", "Europe")),
        ("Belfast, Northern Ireland", ("Belfast", "city", "GB", "Europe")),
        ("Gräfelfing", ("Gräfelfing", "city", "DE", "Europe")),  # under 15,000 people: needs cities1000
        ("Sydney, Australia", ("Sydney", "city", "AU", "APAC")),
        ("Haut-Rhin, Grand Est, France", ("France", "country", "FR", "Europe")),
        ("UK - Remote", ("United Kingdom", "country", "GB", "Europe")),
        ("🇪🇺 Germany (remote)", ("Germany", "country", "DE", "Europe")),
        ("Remote job", ("Anywhere", "worldwide", None, "Worldwide")),
        ("Werken op afstand", ("Anywhere", "worldwide", None, "Worldwide")),
        ("Remote - EMEA", ("EMEA", "region", None, "EMEA")),
        ("Benelux", ("Benelux", "region", None, "Europe")),
        ("Hybrid", ("Hybrid", "unknown", None, None)),
        ("", (None, "unknown", None, None)),
        # a shared name goes to the European place: GeoNames also lists old names, such as Baden for South San
        # Francisco and Malakoff for Oued Sly in Algeria
        ("Baden", ("Baden-Baden", "city", "DE", "Europe")),
        ("Malakoff", ("Malakoff", "city", "FR", "Europe")),
        ("Bayonne", ("Bayonne", "city", "FR", "Europe")),
    ],
)
def test_real_values(locator, raw, expected):
    assert locator.locate(raw) == expected


def test_every_alias_locates_to_its_own_row(locator):
    # This covers all of Jobicy's values, which test_reference_data.py requires to be in locations.csv.
    with open(REFERENCE_DIR / "locations.csv", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))

    mismatches = [
        (row["raw_value"], locator.locate(row["raw_value"]))
        for row in rows
        if locator.locate(row["raw_value"])
        != (row["location_name"], row["location_type"], row["country_code"] or None, row["region"])
    ]
    assert mismatches == []


def test_every_himalayas_location_is_a_country(locator):
    values = json.loads(VOCABULARY.read_text(encoding="utf-8"))["himalayas"]["locations"]

    assert [value for value in values if locator.locate(value).location_type != "country"] == []
