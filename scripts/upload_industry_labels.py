"""Upload the hand labels for the industry model into <catalog>.silver.industry_labels (Phase 5, decision 15).

The labels live in a working folder outside this repository and are never committed: the repository is public, and
its history couldn't delete the key of an expired job. The folder holds
    labels.json    {job_key: {"industry": ..., "batch": ..., "unsure": ...}}    the training labels
    sample.json    [{"n": ..., "job_key": ...}]                                the test set's jobs
    truth35.json   {n: [best industry, other acceptable industries...]}        the test set's labels

Run from the repository root; without --write it only counts:

    python scripts/upload_industry_labels.py "E:/Nexus Learning/skillscout-industry"
    python scripts/upload_industry_labels.py "E:/Nexus Learning/skillscout-industry" --write

--write replaces the whole table. Labels of jobs that are no longer in gold.fct_job_postings are left out, the same
rule that deletes them every night. The connection settings come from .env and are never printed.
"""

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INDUSTRY_LIST = REPO / "databricks" / "reference" / "industry_list.csv"
ROWS_PER_INSERT = 500


def guide_industries() -> set[str]:
    """The industries a label may name: the list's rows without the "<Group>, unspecified" ones."""
    with open(INDUSTRY_LIST, encoding="utf-8", newline="") as file:
        return {row["industry"] for row in csv.DictReader(file) if not row["industry"].endswith(", unspecified")}


def build_rows(labels: dict, sample: list[dict], truth: dict, industries: set[str]) -> list[dict]:
    """One row per labelled job: the test set first (split "test", with its other acceptable industries), then the
    training labels (split "train"). A job in both stays a test job only, so it can never be trained on."""
    rows, test_keys = [], set()
    for entry in sample:
        accepted = truth.get(str(entry["n"]))
        if accepted:
            test_keys.add(entry["job_key"])
            rows.append({"job_key": entry["job_key"], "industry": accepted[0], "also_acceptable": list(accepted[1:]),
                         "split": "test", "batch": None, "unsure": False})
    for job_key, label in labels.items():
        if job_key not in test_keys:
            rows.append({"job_key": job_key, "industry": label["industry"], "also_acceptable": [],
                         "split": "train", "batch": label["batch"], "unsure": bool(label["unsure"])})
    named = {name for row in rows for name in [row["industry"], *row["also_acceptable"]]}
    if named - industries:
        raise ValueError(f"Not industries of the guide: {sorted(named - industries)}")
    keys = Counter(row["job_key"] for row in rows)
    if any(count > 1 for count in keys.values()):
        raise ValueError("A job key appears twice in the test set")
    return rows


def quoted(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def values_sql(row: dict) -> str:
    accepted = "array(" + ", ".join(quoted(name) for name in row["also_acceptable"]) + ")"
    batch = "NULL" if row["batch"] is None else str(int(row["batch"]))
    return (f"({quoted(row['job_key'])}, {quoted(row['industry'])}, cast({accepted} AS ARRAY<STRING>), "
            f"{quoted(row['split'])}, {batch}, {str(row['unsure']).lower()}, current_timestamp())")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="the working folder with labels.json, sample.json and truth35.json")
    parser.add_argument("--write", action="store_true", help="replace the table; without it, only count")
    args = parser.parse_args()

    def read(name):
        return json.loads((args.folder / name).read_text(encoding="utf-8"))

    rows = build_rows(read("labels.json"), read("sample.json"), read("truth35.json"), guide_industries())
    splits = Counter(row["split"] for row in rows)
    print(f"{len(rows)} labelled jobs in the folder: {splits['train']} to train on, {splits['test']} in the test set")

    from databricks import sql
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env")
    catalog = os.environ.get("DATABRICKS_CATALOG", "workspace")
    table, upload, jobs = (f"{catalog}.silver.industry_labels", f"{catalog}.silver.industry_labels_upload",
                           f"{catalog}.gold.fct_job_postings")
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"].removeprefix("https://").rstrip("/"),
        http_path=f"/sql/1.0/warehouses/{os.environ['DATABRICKS_WAREHOUSE_ID']}",
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as connection, connection.cursor() as cursor:
        if not args.write:
            keys = ", ".join(quoted(row["job_key"]) for row in rows)
            cursor.execute(f"SELECT count(*) FROM {jobs} WHERE job_key IN ({keys})")
            print(f"{cursor.fetchone()[0]} of them are jobs in {jobs} now. Nothing was written; add --write to upload.")
            return
        # Loaded into a side table first, so the real one is replaced in a single statement.
        cursor.execute(f"""
            CREATE OR REPLACE TABLE {upload} (
                job_key STRING, industry STRING, also_acceptable ARRAY<STRING>, split STRING, batch INT,
                unsure BOOLEAN, uploaded_at TIMESTAMP
            )
        """)
        for start in range(0, len(rows), ROWS_PER_INSERT):
            chunk = rows[start:start + ROWS_PER_INSERT]
            cursor.execute(f"INSERT INTO {upload} VALUES " + ", ".join(values_sql(row) for row in chunk))
        cursor.execute(f"""
            CREATE OR REPLACE TABLE {table}
            COMMENT 'Hand labels for the industry model: job key, industry, and train or test. Kept between runs; rows of jobs that left gold are deleted (Phase 5, decision 15).'
            AS SELECT * FROM {upload} WHERE job_key IN (SELECT job_key FROM {jobs})
        """)
        cursor.execute(f"DROP TABLE {upload}")
        cursor.execute(f"SELECT split, count(*) FROM {table} GROUP BY split ORDER BY split")
        kept = dict(cursor.fetchall())
    print(f"{table}: {kept.get('train', 0)} to train on, {kept.get('test', 0)} in the test set; "
          f"{len(rows) - sum(kept.values())} left out because their job is no longer in gold")


if __name__ == "__main__":
    main()
