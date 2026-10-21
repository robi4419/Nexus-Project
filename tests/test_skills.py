from collections import Counter
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


def mentions(matcher: SkillMatcher, title: str | None, text: str | None, company: str | None = None) -> dict[str, int]:
    """The match result as {skill: mentions}, which keeps the assertions short."""
    return {found["skill"]: found["mentions"] for found in matcher.match(title, text, company)}


RULE_CASES = [
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
]


@pytest.mark.parametrize(("text", "expected"), RULE_CASES)
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


def test_snippets_show_each_counted_match_in_its_original_context(matcher):
    # The excluded "React Native" is not a React match, but it stays visible around the real one.
    assert matcher.snippets("Python Developer", "React Native and React.", width=10) == [
        {"skill": "Python", "category": "Programming Languages", "field": "title", "snippet": "[Python] Developer"},
        {"skill": "React", "category": "Web & Mobile Frameworks", "field": "text", "snippet": "ative and [React]."},
        {
            "skill": "React Native",
            "category": "Web & Mobile Frameworks",
            "field": "text",
            "snippet": "[React Native] and React",
        },
    ]


def test_snippets_put_each_match_on_one_line(matcher):
    assert matcher.snippets(None, "Tools:\n- Python\n- SQL", width=9) == [
        {"skill": "SQL", "category": "Programming Languages", "field": "text", "snippet": "Python - [SQL]"},
        {"skill": "Python", "category": "Programming Languages", "field": "text", "snippet": "Tools: - [Python] - SQL"},
    ]


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


REAL_TRAPS = [
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
        # added after the 2026-10-19 hand-check
        ("Fleetio is a founding member of the Rails Foundation", "Ruby on Rails", 0),
        ("Load testing with JMeter or Grafana K6", "Grafana", 0),
        ("Advanced LookML Development", "Looker", 1),
        ("Use Claude, ChatGPT and Cursor daily", "Claude", 1),
        ("Jean-Claude leads the team", "Claude", 0),
        ("Move the cursor to the button", "Cursor", 0),
        ("AI tools such as Cursor and Copilot", "GitHub Copilot", 1),
        ("Roll out Microsoft 365 Copilot", "GitHub Copilot", 0),
        ("Roll out Microsoft 365 Copilot", "Microsoft Copilot", 1),
        ("Build MCP servers", "MCP", 1),
        ("Sierra is the leading platform for customer-facing AI agents", "AI Agents", 0),
        ("You have built agentic workflows and enjoy building AI agents", "AI Agents", 2),
        ("Build and fine-tune foundation models", "LLM Fine-tuning", 1),
        ("Fine-tune our sales process", "LLM Fine-tuning", 0),
        ("Prompt/context engineering skills", "Prompt Engineering", 1),
        ("Experience with Entra identity management", "Active Directory", 1),
        ("El candidato entra en el equipo", "Active Directory", 0),
        ("Certifications such as CIA, CAMS or CFE", "Certified Internal Auditor", 1),
        ("Protect the CIA triad", "Certified Internal Auditor", 0),
        ("SSO, SAML and OAuth", "Single Sign-On", 1),
        ("SOX compliance testing", "SOX", 1),
        ("Red Sox fans welcome", "SOX", 0),
        ("Configuration management with Puppet or Chef", "Chef", 1),
        ("Executive Chef wanted", "Chef", 0),
        ("Fluent in Excel/Sheets", "Google Sheets", 1),
        ("Reconcile balance sheets", "Google Sheets", 0),
        ("Zoom, ZoomInfo and Slack", "Zoom", 1),
        ("A positive outlook on growth", "Microsoft Outlook", 0),
        ("Kubernetes on EKS or GKE", "Kubernetes", 3),
]


@pytest.mark.parametrize(("text", "skill", "expected"), REAL_TRAPS)
def test_real_skill_list_traps(real_matcher, text, skill, expected):
    assert mentions(real_matcher, None, text).get(skill, 0) == expected


def test_skill_in_the_employers_name_is_skipped(matcher):
    text = "Python Software Foundation builds Python tools with SQL."

    assert mentions(matcher, None, text) == {"Python": 2, "SQL": 1}
    assert mentions(matcher, None, text, company="Python Software Foundation") == {"SQL": 1}
    assert [found["skill"] for found in matcher.snippets(None, text, company="Python Software Foundation")] == ["SQL"]


def test_real_skill_list_skips_the_employer(real_matcher):
    text = "Supabase is the Postgres development platform. Proficient in SQL."

    assert "Supabase" in mentions(real_matcher, "Support Engineer", text)
    assert "Supabase" not in mentions(real_matcher, "Support Engineer", text, company="Supabase")
    assert "Grafana" not in mentions(real_matcher, None, "Grafana Labs is behind Grafana Cloud.", company="Grafana Labs")


def test_prefilter_never_changes_a_result(matcher, real_matcher, jobicy_page):
    texts = [text for text, _ in RULE_CASES] + [text for text, _, _ in REAL_TRAPS]
    texts += [html_to_text(job["jobDescription"]) for job in jobicy_page["jobs"]]
    for skill_list in (matcher, real_matcher):
        for text in texts:
            for title in (None, "Senior Python Engineer (C#/.NET)"):
                assert skill_list.match(title, text) == skill_list.match(title, text, prefilter=False)
                assert skill_list.snippets(title, text) == skill_list.snippets(title, text, prefilter=False)


def test_prefilter_skips_skills_that_cannot_match(real_matcher):
    with_prefilter = real_matcher._candidates(None, "Python and SQL", None, prefilter=True)
    without = real_matcher._candidates(None, "Python and SQL", None, prefilter=False)

    assert {entry[0] for entry in with_prefilter} >= {"Python", "SQL"}
    assert len(with_prefilter) < len(without) / 10


def test_matcher_version_follows_the_list_and_is_not_the_taxonomy_version():
    version = SkillMatcher(ROWS).matcher_version
    changed = [*ROWS[:-1], {**ROWS[-1], "aliases": "Excel|MS Excel|-Excel at"}]

    assert len(version) == 12
    assert version != SkillMatcher(ROWS).taxonomy_version
    assert SkillMatcher([dict(row) for row in ROWS]).matcher_version == version
    assert SkillMatcher(changed).matcher_version != version


def test_real_skill_list_snippets_agree_with_match(real_matcher, jobicy_page):
    texts = [(job["jobTitle"], html_to_text(job["jobDescription"])) for job in jobicy_page["jobs"]]
    texts.append((None, "Own the Go-to-market plan in Go; React Native and React.js; Looker Studio and Looker."))
    for title, text in texts:
        counted = mentions(real_matcher, title, text)
        snipped = Counter(found["skill"] for found in real_matcher.snippets(title, text))
        assert snipped == counted
