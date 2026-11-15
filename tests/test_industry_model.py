"""The industry model on made-up jobs: the industry list, the model's answers, saving and loading, and scoring."""

import csv
from pathlib import Path

import numpy as np
import pytest

from transform import industry_model
from transform.industry_model import (
    GROUP_OF,
    GROUPS,
    INDUSTRIES,
    NOT_CLASSIFIED,
    IndustryModel,
    industry_list,
    score,
    unspecified,
)

INDUSTRY_LIST_CSV = Path(__file__).parent.parent / "databricks" / "reference" / "industry_list.csv"

# Made-up jobs: three per industry, two industries in each of two groups.
LABELLED = [
    ({"title": "Senior Backend Engineer", "skills": ["Java", "PostgreSQL"]}, "Backend"),
    ({"title": "Backend Developer (Python)", "skills": ["Python", "Django"]}, "Backend"),
    ({"title": "Java Backend Engineer", "skills": ["Java", "Spring Boot"]}, "Backend"),
    ({"title": "Frontend Engineer", "skills": ["React", "TypeScript"]}, "Frontend"),
    ({"title": "Senior Frontend Developer", "skills": ["Vue.js", "CSS"]}, "Frontend"),
    ({"title": "React Frontend Developer", "skills": ["React", "CSS"]}, "Frontend"),
    ({"title": "Account Executive", "skills": ["Salesforce"]}, "Sales & Business Development"),
    ({"title": "Sales Manager, Enterprise", "skills": ["Salesforce", "HubSpot"]}, "Sales & Business Development"),
    ({"title": "Senior Account Executive", "skills": []}, "Sales & Business Development"),
    ({"title": "Marketing Manager", "skills": ["HubSpot", "SEO"]}, "Marketing"),
    ({"title": "Content Marketing Manager", "skills": ["SEO"]}, "Marketing"),
    ({"title": "Growth Marketing Lead", "skills": ["Google Analytics"]}, "Marketing"),
]
NEW_JOBS = [
    {"title": "Backend Engineer", "skills": ["Java"]},
    {"title": "Enterprise Account Executive", "skills": ["Salesforce"]},
    {"title": "Frontend Developer", "skills": ["React"]},
]


@pytest.fixture(scope="module")
def model():
    return IndustryModel().fit([job for job, _ in LABELLED], [industry for _, industry in LABELLED])


# --- the industry list ---------------------------------------------------------------------------------------------


def test_the_guide_has_34_industries_in_9_groups_plus_not_classified():
    assert len(INDUSTRIES) == len(set(INDUSTRIES)) == 35
    assert len(GROUPS) == 10
    assert GROUPS[NOT_CLASSIFIED] == [NOT_CLASSIFIED]
    assert GROUP_OF["Backend"] == "Software"


def test_industry_list_adds_an_unspecified_row_only_to_groups_of_several_industries():
    names = [name for name, _, _ in industry_list()]
    assert unspecified("Software") == "Software, unspecified"
    assert "Software, unspecified" in names
    assert "Hardware, unspecified" not in names  # one industry: sure of the group means sure of the industry
    assert names[-1] == NOT_CLASSIFIED
    assert len(names) == len(set(names)) == 35 + 8
    assert [order for _, _, order in industry_list()] == list(range(1, len(names) + 1))


def test_industry_list_csv_is_the_list_in_the_code():
    with open(INDUSTRY_LIST_CSV, encoding="utf-8", newline="") as file:
        rows = [(row["industry"], row["industry_group"], int(row["sort_order"])) for row in csv.DictReader(file)]
    assert rows == industry_list()


# --- the model's answers -------------------------------------------------------------------------------------------


def test_predicts_the_industry_and_its_group(model):
    answers = model.predict(NEW_JOBS)
    assert [(industry, group) for industry, _, group, _ in answers] == [
        ("Backend", "Software"),
        ("Sales & Business Development", "Business"),
        ("Frontend", "Software"),
    ]


def test_a_groups_probability_is_the_sum_over_its_industries(model):
    proba = model.proba(NEW_JOBS)
    assert np.allclose(proba.sum(axis=1), 1)
    software = [model.classes.index("Backend"), model.classes.index("Frontend")]
    for row, (_, probability, group, group_probability) in zip(proba, model.predict(NEW_JOBS)):
        assert group_probability >= probability
        if group == "Software":
            assert group_probability == pytest.approx(row[software].sum())


def test_a_job_without_title_or_skills_still_gets_an_answer(model):
    answers = model.predict([{"title": None, "skills": None}, {}])
    assert len(answers) == 2
    assert all(industry in INDUSTRIES for industry, *_ in answers)


def test_no_jobs_give_no_answers(model):
    assert model.predict([]) == []


def test_a_skill_name_with_spaces_stays_one_feature(model):
    assert {"Spring Boot", "Google Analytics", "Vue.js"} <= set(model.skills.vocabulary_)


def test_fit_rejects_an_industry_the_guide_does_not_have():
    with pytest.raises(ValueError, match="Web Development"):
        IndustryModel().fit([job for job, _ in LABELLED], ["Web Development"] * len(LABELLED))


# --- saving and loading --------------------------------------------------------------------------------------------


def test_a_saved_model_gives_the_same_answers(model, tmp_path):
    path = str(tmp_path / "model.joblib")
    model.save(path)
    loaded = IndustryModel.load(path)
    assert loaded.classes == model.classes
    assert np.allclose(loaded.proba(NEW_JOBS), model.proba(NEW_JOBS))
    assert loaded.predict(NEW_JOBS) == model.predict(NEW_JOBS)


def test_load_refuses_a_model_saved_by_another_scikit_learn_version(model, tmp_path, monkeypatch):
    path = str(tmp_path / "model.joblib")
    model.save(path)
    monkeypatch.setattr(industry_model.sklearn, "__version__", "0.0.0")
    with pytest.raises(ValueError, match="scikit-learn"):
        IndustryModel.load(path)


# --- scoring -------------------------------------------------------------------------------------------------------


def test_score_counts_acceptable_answers_and_answers_at_the_threshold():
    predictions = [
        ("Backend", 0.9, "Software", 0.95),  # the best answer, answered
        ("Frontend", 0.4, "Software", 0.8),  # acceptable but not the best; only the group is answered
        ("Marketing", 0.7, "Business", 0.7),  # wrong industry, right group, answered
        ("Marketing", 0.3, "Business", 0.45),  # wrong, and not answered
    ]
    acceptable = [["Backend"], ["Full-stack", "Frontend"], ["Sales & Business Development"], ["Backend"]]
    assert score(predictions, acceptable, sure=0.5) == {
        "jobs": 4,
        "industry_right": 0.5,
        "best_right": 0.25,
        "answered": 0.5,
        "right_when_answered": 0.5,
        "group_right": 0.75,
        "group_answered": 0.75,
        "group_right_when_answered": 1.0,
    }


def test_score_needs_one_label_list_per_prediction():
    with pytest.raises(ValueError):
        score([("Backend", 0.9, "Software", 0.95)], [], sure=0.5)
