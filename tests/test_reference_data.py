"""Checks the reference CSVs in databricks/reference/ so a typo is caught before it reaches Databricks."""

import csv
from pathlib import Path

import pytest

REFERENCE_DIR = Path(__file__).parent.parent / "databricks" / "reference"

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
REGIONS = {"North America", "LATAM", "Europe", "Middle East & Africa", "APAC", "EMEA", "Worldwide"}

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
