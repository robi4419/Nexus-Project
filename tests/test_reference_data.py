"""Checks the reference CSVs in databricks/reference/ so a typo is caught before it reaches Databricks."""

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).parent.parent / "databricks" / "reference"
VOCABULARY = Path(__file__).parent / "fixtures" / "source_vocabulary.json"

SOURCES = {"jobicy", "himalayas", "arbeitnow"}
# Jobicy's 22 industries are the base list; these four were added in Phase 2b where no Jobicy industry fits.
NEW_INDUSTRIES = {"Hardware & Electronics", "Research & Science", "Engineering & Manufacturing", "Logistics & Supply Chain"}
JOB_TYPES = {"Full-Time", "Part-Time", "Contract", "Internship", "Temporary"}
SENIORITY_LEVELS = {"Intern", "Junior", "Mid", "Senior", "Lead", "Director", "Executive"}
MAPPING_TARGETS = {"industries.csv": "industry", "job_types.csv": "job_type", "levels.csv": "seniority"}

SKILL_CATEGORIES = {
    "Programming Languages",
    "Web & Mobile Frameworks",
    "Data Engineering",
    "Data Science & AI",
    "Analytics & BI",
    "Databases",
    "Cloud",
    "DevOps & Infrastructure",
    "Security",
    "Testing & QA",
    "CRM & Sales Tools",
    "Marketing & SEO Tools",
    "Customer Support Tools",
    "Finance & ERP",
    "Productivity & Project Management",
    "Design Tools",
    "HR & Recruiting Tools",
    "Certifications",
}
LOCATION_TYPES = {"country", "region", "worldwide"}
# Antarctica: the uninhabited territories some Himalayas jobs list among every country (Phase 2b, decision 28)
REGIONS = {"North America", "LATAM", "Europe", "Middle East & Africa", "APAC", "EMEA", "Worldwide", "Antarctica"}

# Jobicy's official location list (GET /api/v2/remote-jobs?get=locations, 2026-10-15).
JOBICY_LOCATIONS = [
    "Anywhere", "APAC", "EMEA", "LATAM", "Argentina", "Australia", "Austria", "Belgium", "Brazil", "Bulgaria",
    "Canada", "China", "Costa Rica", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Europe", "Finland",
    "France", "Germany", "Greece", "Hong Kong", "Hungary", "Ireland", "Israel", "Italy", "Japan", "Latvia",
    "Lithuania", "Malaysia", "Mexico", "Netherlands", "New Zealand", "Norway", "Philippines", "Poland", "Portugal",
    "Romania", "Serbia", "Singapore", "Slovakia", "Slovenia", "South Korea", "Spain", "Sweden", "Switzerland",
    "Thailand", "Türkiye", "UAE", "UK", "Ukraine", "USA", "Vietnam",
]


def read_csv(name: str) -> list[dict]:
    with open(REFERENCE_DIR / name, encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


@pytest.fixture(scope="module")
def skills() -> list[dict]:
    return read_csv("skills.csv")


@pytest.fixture(scope="module")
def locations() -> list[dict]:
    return read_csv("locations.csv")


@pytest.fixture(scope="module")
def countries() -> list[dict]:
    return read_csv("countries.csv")


@pytest.fixture(scope="module")
def cities() -> dict[str, dict]:
    return {row["alias"]: row for row in read_csv("cities.csv")}


def aliases_of(skill: dict) -> list[str]:
    """The phrases that count as a mention (exclusion phrases start with '-' and are left out)."""
    return [alias for alias in skill["aliases"].split("|") if not alias.startswith("-")]


# --- skills.csv ---------------------------------------------------------------------------------------------


def test_skills_columns(skills):
    assert list(skills[0]) == ["skill", "category", "aliases", "case_sensitive"]


def test_skill_names_are_unique(skills):
    names = [row["skill"] for row in skills]
    assert len(names) == len(set(names))


def test_categories_are_known(skills):
    assert {row["category"] for row in skills} <= SKILL_CATEGORIES


def test_case_sensitive_is_true_or_false(skills):
    assert {row["case_sensitive"] for row in skills} <= {"true", "false"}


def test_every_skill_has_an_alias_and_no_blank_ones(skills):
    for row in skills:
        parts = row["aliases"].split("|")
        assert aliases_of(row), f"{row['skill']} has no aliases"
        assert all(part.strip() == part and part.strip("-") for part in parts), f"blank or padded alias in {row['skill']}"


def test_no_alias_belongs_to_two_skills(skills):
    owner: dict[str, str] = {}
    for row in skills:
        for alias in aliases_of(row):
            key = alias if row["case_sensitive"] == "true" else alias.lower()
            assert owner.get(key, row["skill"]) == row["skill"], f"'{alias}' is used by {owner[key]} and {row['skill']}"
            owner[key] = row["skill"]


def test_no_duplicate_aliases_within_a_skill(skills):
    for row in skills:
        aliases = aliases_of(row)
        keys = aliases if row["case_sensitive"] == "true" else [alias.lower() for alias in aliases]
        assert len(keys) == len(set(keys)), f"duplicate alias in {row['skill']}"


# --- locations.csv ------------------------------------------------------------------------------------------


def test_locations_columns(locations):
    assert list(locations[0]) == ["raw_value", "location_name", "location_type", "country_code", "region"]


def test_raw_values_are_unique_ignoring_case(locations):
    values = [row["raw_value"].lower() for row in locations]
    assert len(values) == len(set(values))


def test_location_types_and_regions_are_known(locations):
    assert {row["location_type"] for row in locations} <= LOCATION_TYPES
    assert {row["region"] for row in locations} <= REGIONS


def test_countries_have_iso_codes_and_regions_do_not(locations):
    for row in locations:
        code = row["country_code"]
        if row["location_type"] == "country":
            assert len(code) == 2 and code.isupper(), f"bad country_code for {row['raw_value']}"
        else:
            assert code == "", f"{row['raw_value']} is not a country but has a country_code"


def test_every_jobicy_location_is_mapped(locations):
    missing = set(JOBICY_LOCATIONS) - {row["raw_value"] for row in locations}
    assert missing == set()


# --- countries.csv and cities.csv (generated by scripts/build_geo_reference.py from GeoNames) ----------------


def test_countries_columns_codes_and_regions(countries):
    codes = [row["country_code"] for row in countries]

    assert list(countries[0]) == ["country_code", "country_name", "region"]
    assert len(codes) == len(set(codes)) and all(len(code) == 2 and code.isupper() for code in codes)
    assert [row["country_name"] for row in countries if row["country_name"] != row["country_name"].strip()] == []
    assert {row["region"] for row in countries} <= REGIONS - {"EMEA", "Worldwide"}


def test_locations_agree_with_countries(locations, countries):
    by_code = {row["country_code"]: (row["country_name"], row["region"]) for row in countries}
    mismatches = [
        (row["raw_value"], (row["location_name"], row["region"]), by_code.get(row["country_code"]))
        for row in locations
        if row["location_type"] == "country" and (row["location_name"], row["region"]) != by_code.get(row["country_code"])
    ]
    assert mismatches == []


def test_cities_have_lowercase_aliases_and_known_countries(cities, countries):
    first = next(iter(cities.values()))

    assert list(first) == ["alias", "city", "country_code", "population"]
    assert all(alias == alias.lower() for alias in cities)
    assert {row["country_code"] for row in cities.values()} <= {row["country_code"] for row in countries}


@pytest.mark.parametrize(
    ("alias", "city", "country"),
    [
        ("münchen", "Munich", "DE"),
        ("munich", "Munich", "DE"),
        ("cologne", "Köln", "DE"),
        ("frankfurt am main", "Frankfurt am Main", "DE"),
        ("zurich", "Zürich", "CH"),
        ("den haag", "The Hague", "NL"),
        ("london", "London", "GB"),
        ("paris", "Paris", "FR"),  # not Paris, Texas: a European place wins, then the most populous
        ("baden", "Baden-Baden", "DE"),  # not South San Francisco, which GeoNames also lists as Baden
    ],
)
def test_known_cities(cities, alias, city, country):
    assert (cities[alias]["city"], cities[alias]["country_code"]) == (city, country)


# --- industries.csv, job_types.csv, levels.csv (each source's values -> ours; empty target = reviewed, no mapping) --


@pytest.fixture(scope="module")
def vocabulary() -> dict:
    return json.loads(VOCABULARY.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", MAPPING_TARGETS)
def test_mapping_columns_targets_and_unique_values(vocabulary, name):
    target = MAPPING_TARGETS[name]
    allowed = {
        "industry": set(vocabulary["jobicy"]["industries"]) | NEW_INDUSTRIES,
        "job_type": JOB_TYPES,
        "seniority": SENIORITY_LEVELS,
    }[target]
    rows = read_csv(name)
    keys = Counter((row["source"], row["raw_value"].lower()) for row in rows)

    assert list(rows[0]) == ["source", "raw_value", target]
    assert {row["source"] for row in rows} <= SOURCES
    assert {row[target] for row in rows} <= allowed | {""}
    assert [key for key, count in keys.items() if count > 1] == []  # matching ignores case
    assert all(row["raw_value"] and row["raw_value"] == row["raw_value"].strip() for row in rows)


def test_jobicy_industries_map_to_themselves(vocabulary):
    jobicy = {row["raw_value"]: row["industry"] for row in read_csv("industries.csv") if row["source"] == "jobicy"}

    assert jobicy == {industry: industry for industry in vocabulary["jobicy"]["industries"]}


@pytest.mark.parametrize(
    ("name", "source", "field"),
    [
        ("industries.csv", "himalayas", "industries"),
        ("job_types.csv", "jobicy", "job_types"),
        ("job_types.csv", "himalayas", "job_types"),
        ("job_types.csv", "arbeitnow", "job_types"),
        ("levels.csv", "jobicy", "levels"),
        ("levels.csv", "himalayas", "levels"),
    ],
)
def test_every_observed_value_is_classified(vocabulary, name, source, field):
    listed = {row["raw_value"].lower() for row in read_csv(name) if row["source"] == source}

    assert [value for value in vocabulary[source][field] if value.lower() not in listed] == []


def test_every_frequent_arbeitnow_tag_is_classified(vocabulary):
    # A tag can describe an industry ("Finance") or a level ("Team Leader"), so either file counts.
    listed = {
        row["raw_value"].lower()
        for name in ("industries.csv", "levels.csv")
        for row in read_csv(name)
        if row["source"] == "arbeitnow"
    }

    assert [tag for tag in vocabulary["arbeitnow"]["industries"] if tag.lower() not in listed] == []
