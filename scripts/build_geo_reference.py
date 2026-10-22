"""Build databricks/reference/countries.csv and cities.csv from GeoNames (https://www.geonames.org, CC BY 4.0).

Run by hand to refresh the geography reference data, then review the diff and commit the two CSVs:

    python scripts/build_geo_reference.py
"""

import csv
import io
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))  # makes `import ingestion` work when this file is run as a script

from ingestion.common.http import build_session  # noqa: E402

GEONAMES = "https://download.geonames.org/export/dump"
REFERENCE = REPO / "databricks" / "reference"

# GeoNames gives each country a continent; our regions follow it, with the overrides below.
CONTINENT_REGIONS = {"EU": "Europe", "AF": "Middle East & Africa", "AS": "APAC", "OC": "APAC", "SA": "LATAM", "NA": "LATAM"}
REGION_OVERRIDES = {
    # North America means the US and Canada (plus Bermuda, Greenland, Saint Pierre); the rest of it is LATAM.
    **dict.fromkeys(["US", "CA", "BM", "GL", "PM"], "North America"),
    # The Middle East, which GeoNames puts in Asia.
    **dict.fromkeys(["AE", "BH", "IL", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "QA", "SA", "SY", "YE"], "Middle East & Africa"),
    # Countries we count as Europe although GeoNames may put them in Asia (as in locations.csv for Türkiye).
    **dict.fromkeys(["TR", "CY", "GE", "AM", "AZ"], "Europe"),
}
# Names as the rest of the project writes them (locations.csv), where GeoNames differs.
NAME_OVERRIDES = {"TR": "Türkiye", "CZ": "Czechia", "NL": "Netherlands"}

# A usable alternate city name: Latin letters (with accents), spaces, apostrophes, dots or hyphens, and at least one
# lowercase letter, which leaves out codes such as "MUC" or "NYC" that could clash with other words.
LATIN_NAME = re.compile(r"[A-Za-zÀ-ÖØ-öø-ɏ][A-Za-zÀ-ÖØ-öø-ɏ' .\-]*")


def countries(session) -> dict[str, tuple[str, str]]:
    """{ISO code: (name, region)} for every country GeoNames lists, except Antarctica's territories."""
    text = session.get(f"{GEONAMES}/countryInfo.txt").text
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        code, name, continent = fields[0], fields[4].strip(), fields[8]  # BQ's name ends in a space
        if continent == "AN":
            continue
        result[code] = (NAME_OVERRIDES.get(code, name), REGION_OVERRIDES.get(code, CONTINENT_REGIONS[continent]))
    return result


def cities(session, regions: dict[str, str]) -> list[tuple[str, str, str, int]]:
    """(alias, city, country code, population) rows for every place with over 1,000 people: every name a place goes by,
    lowercased and kept once. When places share a name, a European one wins, then the most populous one. Only
    Arbeitnow, a European job board, gives city names, and GeoNames lists old and foreign names too: by population
    alone "baden" would be South San Francisco (once called Baden) and "sion" Jerusalem (Zion)."""
    archive = zipfile.ZipFile(io.BytesIO(session.get(f"{GEONAMES}/cities1000.zip").content))
    best: dict[str, tuple[tuple[bool, int], tuple[str, str, str, int]]] = {}
    with archive.open("cities1000.txt") as file:
        for line in io.TextIOWrapper(file, encoding="utf-8"):
            fields = line.rstrip("\n").split("\t")
            name, ascii_name, alternates, country, population = fields[1], fields[2], fields[3], fields[8], int(fields[14])
            if country not in regions:
                continue
            aliases = {name, ascii_name} | {
                alias for alias in alternates.split(",")
                if len(alias) >= 3 and LATIN_NAME.fullmatch(alias) and any(char.islower() for char in alias)
            }
            rank = (regions[country] == "Europe", population)
            for alias in {alias.lower() for alias in aliases}:
                if alias not in best or rank > best[alias][0]:
                    best[alias] = (rank, (alias, name, country, population))
    return sorted(row for _, row in best.values())


def write_csv(path: Path, header: list[str], rows) -> None:
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"{path.relative_to(REPO)}: {sum(1 for _ in open(path, encoding='utf-8')) - 1} rows")


def main() -> None:
    session = build_session()
    country_rows = countries(session)
    write_csv(
        REFERENCE / "countries.csv",
        ["country_code", "country_name", "region"],
        [(code, name, region) for code, (name, region) in sorted(country_rows.items())],
    )
    regions = {code: region for code, (_, region) in country_rows.items()}
    write_csv(REFERENCE / "cities.csv", ["alias", "city", "country_code", "population"], cities(session, regions))


if __name__ == "__main__":
    main()
