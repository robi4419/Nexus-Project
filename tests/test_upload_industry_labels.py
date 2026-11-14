"""The label upload's rows, built from made-up labels (the real ones are never in this repository)."""

import pytest

from scripts.upload_industry_labels import build_rows, guide_industries, values_sql

LABELS = {
    "key-a": {"industry": "Backend", "batch": 1, "unsure": False},
    "key-b": {"industry": "Marketing", "batch": 2, "unsure": True},
    "key-t": {"industry": "Frontend", "batch": 2, "unsure": False},  # also a test job: the test set wins
}
SAMPLE = [{"n": 1, "job_key": "key-t"}, {"n": 2, "job_key": "key-u"}, {"n": 3, "job_key": "key-unjudged"}]
TRUTH = {"1": ["Full-stack", "Frontend"], "2": ["Sales & Business Development"]}


def test_guide_industries_leave_out_the_unspecified_rows():
    industries = guide_industries()
    assert len(industries) == 35
    assert "Software Engineering, general" in industries
    assert "Software, unspecified" not in industries


def test_rows_hold_the_test_set_and_the_training_labels():
    rows = {row["job_key"]: row for row in build_rows(LABELS, SAMPLE, TRUTH, guide_industries())}
    assert set(rows) == {"key-a", "key-b", "key-t", "key-u"}  # the unjudged sample job has no label
    assert rows["key-t"] == {"job_key": "key-t", "industry": "Full-stack", "also_acceptable": ["Frontend"],
                             "split": "test", "batch": None, "unsure": False}
    assert rows["key-b"] == {"job_key": "key-b", "industry": "Marketing", "also_acceptable": [],
                             "split": "train", "batch": 2, "unsure": True}


def test_an_industry_outside_the_guide_is_refused():
    with pytest.raises(ValueError, match="Web Development"):
        build_rows({"key-a": {"industry": "Web Development", "batch": 1, "unsure": False}}, [], {}, guide_industries())


def test_values_sql_quotes_text_and_writes_arrays():
    row = {"job_key": "k'1", "industry": "Software Engineering, general", "also_acceptable": ["Backend"],
           "split": "test", "batch": None, "unsure": False}
    assert values_sql(row) == (
        "('k\\'1', 'Software Engineering, general', cast(array('Backend') AS ARRAY<STRING>), "
        "'test', NULL, false, current_timestamp())"
    )
