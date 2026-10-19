import pytest

from transform.seniority import seniority


@pytest.mark.parametrize(
    ("title", "source_level", "expected"),
    [
        # one or more titles per rule (real Jobicy titles where possible)
        ("Chief Technology Officer", "Director", ("Executive", "title")),
        ("Regional VP, Sales", "Director", ("Executive", "title")),
        ("SVP of Engineering", "Any", ("Executive", "title")),
        ("Vice President, Partnership Sales", "Director", ("Executive", "title")),
        ("President - Business Unit", "Director", ("Executive", "title")),
        ("Head of Engineering", "Director", ("Director", "title")),
        ("Team Lead Software Engineer", "Senior", ("Lead", "title")),
        ("Principal Product Manager", "Senior", ("Lead", "title")),
        ("Staff Data Engineer", "Director", ("Lead", "title")),
        ("SecOps Security Engineer (Staff-level, L6)", "Senior", ("Lead", "title")),
        ("Sr. Software Engineer, Cloud Platform", "Senior", ("Senior", "title")),
        ("Senior Account Executive, Enterprise", "Director", ("Senior", "title")),
        ("SENIOR DATA ENGINEER", "Any", ("Senior", "title")),
        ("Intermediate Data Analyst", "Any", ("Mid", "title")),
        ("Junior QA Engineer - US Remote", "Senior", ("Junior", "title")),
        ("Entry-level communications specialist", "Entry-Level, Junior", ("Junior", "title")),
        ("Graduate HR Generalist - APAC", "Entry-Level, Junior", ("Junior", "title")),
        ("New Grad Software Engineer", "Any", ("Junior", "title")),
        ("Software Engineer, Early Career", "Any", ("Junior", "title")),
        ("Customer Success Associate", "Any", ("Junior", "title")),
        ("Applied Scientist Intern", "Entry-Level, Junior", ("Intern", "title")),
        ("Data Engineering Apprentice", "Any", ("Intern", "title")),
        # rule order: the first match wins
        ("Associate Director, Tax", "Director", ("Director", "title")),
        ("Sr. Director, Renewals Operations", "Director", ("Director", "title")),
        ("Sr. Staff Machine Learning Systems Engineer", "Senior", ("Lead", "title")),
        ("Senior / Staff Threat Intelligence Analyst, Hacks", "Director", ("Lead", "title")),
        ("Mid/Sr. Product Engineer, Intelligence", "Senior", ("Senior", "title")),
        ("Business Development Manager (Junior to Mid-Level) – Hong Kong", "Senior", ("Mid", "title")),
        # traps: a seniority word that doesn't mean seniority
        ("Executive Assistant to the CEO", "Director", ("Unspecified", "none")),
        ("Principal Engineer (AI, Office of the CEO)", "Director", ("Lead", "title")),
        ("Senior Staff Operations Manager, Office of the President (PED)", "Director", ("Lead", "title")),
        ("Member of Technical Staff (ML)", "Senior", ("Senior", "source_level")),
        ("Clinical Research Associate", "Midweight", ("Mid", "source_level")),
        ("Sr Clinical Research Associate (Serbia)", "Senior", ("Senior", "title")),
        ("Lead Generation Specialist", "Any", ("Unspecified", "none")),
        ("Staff Accountant", "Midweight", ("Mid", "source_level")),
        ("Senior Staff Accountant", "Any", ("Senior", "title")),
        ("Account Executive II, Mid-Market", "Director", ("Unspecified", "none")),
        ("CRO Specialist", "Any", ("Unspecified", "none")),
        ("Internal Auditor", "Any", ("Unspecified", "none")),
        ("Leadership Development Partner", "Midweight", ("Mid", "source_level")),
        # no title rule: fall back to the source's level
        ("Product Manager", "Senior", ("Senior", "source_level")),
        ("Data Analyst", "Midweight", ("Mid", "source_level")),
        ("Data Analyst", "Entry-Level, Junior", ("Junior", "source_level")),
        ("Data Analyst", " SENIOR ", ("Senior", "source_level")),
        ("Data Analyst", "Director", ("Unspecified", "none")),
        ("Data Analyst", "Any", ("Unspecified", "none")),
    ],
)
def test_seniority(title, source_level, expected):
    assert seniority(title, source_level) == expected


def test_missing_values():
    assert seniority(None, None) == ("Unspecified", "none")
    assert seniority(None, "Senior") == ("Senior", "source_level")
    assert seniority("Staff Data Engineer", None) == ("Lead", "title")
