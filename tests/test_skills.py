from pathlib import Path

import pytest

from transform.skills import SkillMatcher
from transform.text import html_to_text

SKILLS_CSV = Path(__file__).parent.parent / "databricks" / "reference" / "skills.csv"

# A small made-up skill list, so each rule can be tested on its own.
ROWS = [
    {"skill": "Java", "category": "Programming Languages", "aliases": "Java", "case_sensitive": "false"},
    {"skill": "JavaScript", "category": "Programming Languages", "aliases": "JavaScript|JS", "case_sensitive": "false"},
    {"skill": "C", "category": "Programming Languages", "aliases": "C programming|C/C++", "case_sensitive": "true"},
    {"skill": "C++", "category": "Programming Languages", "aliases": "C++", "case_sensitive": "false"},
    {"skill": "C#", "category": "Programming Languages", "aliases": "C#", "case_sensitive": "false"},
    {"skill": "SQL", "category": "Programming Languages", "aliases": "SQL", "case_sensitive": "true"},
    {"skill": "Python", "category": "Programming Languages", "aliases": "Python", "case_sensitive": "false"},
    {"skill": "Go", "category": "Programming Languages", "aliases": "Go|Golang|-Go-to-market|-Go deep", "case_sensitive": "true"},
    {"skill": ".NET", "category": "Web & Mobile Frameworks", "aliases": ".NET|ASP.NET", "case_sensitive": "false"},
    {"skill": "Node.js", "category": "Web & Mobile Frameworks", "aliases": "Node.js", "case_sensitive": "false"},
    {"skill": "Vue.js", "category": "Web & Mobile Frameworks", "aliases": "Vue|Vue.js", "case_sensitive": "false"},
    {"skill": "React", "category": "Web & Mobile Frameworks", "aliases": "React|-React Native", "case_sensitive": "true"},
    {"skill": "React Native", "category": "Web & Mobile Frameworks", "aliases": "React Native", "case_sensitive": "true"},
    {"skill": "Apache Airflow", "category": "Data Engineering", "aliases": "Airflow|Apache Airflow", "case_sensitive": "false"},
    {"skill": "Excel", "category": "Productivity & Project Management", "aliases": "Excel|-Excel at", "case_sensitive": "true"},
]


@pytest.fixture(scope="module")
def matcher() -> SkillMatcher:
    return SkillMatcher(ROWS)


@pytest.fixture(scope="module")
def real_matcher() -> SkillMatcher:
    return SkillMatcher.from_csv(SKILLS_CSV)


def mentions(matcher: SkillMatcher, title: str | None, text: str | None) -> dict[str, int]:
    """The match result as {skill: mentions}, which keeps the assertions short."""
    return {found["skill"]: found["mentions"] for found in matcher.match(title, text)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # whole words only
        ("We use JavaScript", {"JavaScript": 1}),
        ("Java and JavaScript", {"Java": 1, "JavaScript": 1}),
        ("Built on Node.js", {"Node.js": 1}),
        ("MySQL and NoSQL stores", {}),
        ("Python3 or python", {"Python": 1}),
        ("We use Python.", {"Python": 1}),
        ("C# and .NET, ASP.NET", {"C#": 1, ".NET": 2}),
        # different skills may share a phrase
        ("Strong C/C++ skills", {"C": 1, "C++": 1}),
        # within one skill, a piece of text counts once, as its longest alias
        ("Vue, Vue.js and Apache Airflow", {"Vue.js": 2, "Apache Airflow": 1}),
        # a space in an alias matches any whitespace
        ("React  Native\nor React\nNative", {"React Native": 2}),
        # case: SQL, Go and Excel are case-sensitive, Python isn't
        ("SQL, sql, PYTHON", {"SQL": 1, "Python": 1}),
        ("Go, Golang and Go-based services; we go", {"Go": 3}),
        # exclusion phrases are blanked out first, and they ignore case even for a case-sensitive skill
        ("React Native and React", {"React": 1, "React Native": 1}),
        ("Excel at teamwork, build Excel reports", {"Excel": 1}),
        ("Go-To-Market plans: Go deep, GO-TO-MARKET", {}),
    ],
)
def test_matching_rules(matcher, text, expected):
    assert mentions(matcher, None, text) == expected


def test_result_has_category_mentions_and_in_title(matcher):
    assert matcher.match("Senior Python Engineer", "Python and SQL. More Python.") == [
        {"skill": "SQL", "category": "Programming Languages", "mentions": 1, "in_title": False},
        {"skill": "Python", "category": "Programming Languages", "mentions": 3, "in_title": True},
    ]


def test_missing_title_or_text(matcher):
    assert matcher.match(None, None) == []
    assert mentions(matcher, "Python Developer", None) == {"Python": 1}


def test_skill_without_aliases_is_rejected():
    rows = [{"skill": "React", "category": "Web & Mobile Frameworks", "aliases": "-React Native", "case_sensitive": "true"}]
    with pytest.raises(ValueError, match="no aliases"):
        SkillMatcher(rows)


def test_taxonomy_version_is_stable_and_follows_content():
    version = SkillMatcher(ROWS).taxonomy_version
    changed = [*ROWS[:-1], {**ROWS[-1], "aliases": "Excel|MS Excel|-Excel at"}]

    assert len(version) == 12
    assert SkillMatcher([dict(row) for row in ROWS]).taxonomy_version == version
    assert SkillMatcher(changed).taxonomy_version != version


# --- the real skills.csv -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, {"Salesforce": 1, "HubSpot": 1}),
        (1, {"Python": 1, "SQL": 1, "Go": 1, "Apache Airflow": 1, "dbt": 1, "Databricks": 1, "Kubernetes": 2}),
    ],
)
def test_real_skill_list_on_jobicy_jobs(real_matcher, jobicy_page, index, expected):
    job = jobicy_page["jobs"][index]

    assert mentions(real_matcher, job["jobTitle"], html_to_text(job["jobDescription"])) == expected


@pytest.mark.parametrize(
    ("text", "skill", "expected"),
    [
        ("Trained in DBT therapy.", "dbt", 0),
        ("We model data with dbt.", "dbt", 1),
        ("Advanced Excel skills; you excel at teamwork", "Excel", 1),
        ("Dashboards in Looker Studio", "Looker", 0),
        ("Dashboards in Looker Studio", "Looker Studio", 1),
        ("Mobile apps in React Native", "React", 0),
        ("We go fast. Experience with Golang", "Go", 1),
        ("Backend services in golang", "Go", 1),
        ("Python, Go, or Java", "Go", 1),
        ("Own the Go-to-market plan and the Go-Live date", "Go", 0),
        ("Be a Go-To customer expert", "Go", 0),
        ("Go to write our application code", "Go", 1),
        ("Go deep on the problem and Go the extra mile", "Go", 0),
        ("Go/No-Go reviews", "Go", 0),
        ("Strong C/C++ skills", "C", 1),
        ("Strong C/C++ skills", "C++", 1),
        ("Built with Node.js", "JavaScript", 0),
        ("Greenhouse Gas reporting", "Greenhouse", 0),
        ("greenhouse gas reporting", "Greenhouse", 0),
        ("Recruiting in Greenhouse", "Greenhouse", 1),
        ("AWS and Amazon Web Services", "AWS", 2),
    ],
)
def test_real_skill_list_traps(real_matcher, text, skill, expected):
    assert mentions(real_matcher, None, text).get(skill, 0) == expected
