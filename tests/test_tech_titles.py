import csv
from pathlib import Path

import pytest

from transform.tech_titles import TECH_CATEGORIES, tech_category

INDUSTRIES_CSV = Path(__file__).parent.parent / "databricks" / "reference" / "industries.csv"


# Made-up titles shaped like the Himalayas jobs without a parent category sampled on 2026-10-30 (real Himalayas jobs
# aren't stored in the repo).
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # one or more titles per category
        ("Senior Software Engineer, Payments", "Developer"),
        ("Full Stack Developer (React, Node.js)", "Developer"),
        ("IT Support Specialist", "Developer"),
        ("Service Desk Analyst - Night Shift", "Developer"),
        ("Cybersecurity Analyst II", "Developer"),
        ("Incident Response Consultant", "Developer"),
        ("Linux Systems Administrator", "Developer"),
        ("Engineering Manager, Platform", "Developer"),
        ("Desarrollador Backend Senior", "Developer"),
        ("Lead Data Engineer", "Data Science"),
        ("Machine Learning Engineer, Ranking", "Data Science"),
        ("Senior BI Developer (Power BI)", "Data Science"),
        ("Biostatistician", "Data Science"),
        ("Analista de Datos Senior", "Data Science"),
        ("Senior Product Manager, Checkout", "Product"),
        ("Head of Product", "Product"),
        ("Technical Program Manager", "Product"),
        ("Senior UX Designer", "Design"),
        ("Motion Graphics Designer", "Design"),
        ("WordPress Website Designer", "Design"),
        ("Embedded Firmware Engineer", "Hardware Engineer"),
        ("FPGA Design Engineer", "Hardware Engineer"),
        ("Research Scientist, Protein Design", "Research & Development"),
        ("Computational Chemist", "Research & Development"),
        # enterprise systems: the platform plus a systems role
        ("SAP FICO Senior Consultant", "Developer"),
        ("Workday HCM Analyst", "Developer"),
        ("Epic Ambulatory Application Analyst", "Developer"),
        ("Salesforce Administrator", "Developer"),
        ("Senior HRIS Specialist", "Developer"),
        ("Payroll Specialist with SAP experience", None),
        # the first match wins
        ("Data Platform Architect", "Data Science"),
        ("Product Designer", "Design"),
        ("Senior Graphics Engineer", "Developer"),
        ("NLP Engineer, Natural Language Understanding", "Data Science"),
        ("Large Language Model Engineer", "Data Science"),
        ("Solutions Engineer (Pre-Sales)", "Developer"),
        ("Sales Engineer, EMEA", "Developer"),
        # AI-training gigs, even in a Tech field
        ("Computational Chemist - Fully Remote | Upto $70/hr", None),
        ("Audio Engineer - AI Trainer", None),
        ("Python Teaching Experts", None),
        ("AI Safety Specialist - Evaluation Expert", None),
        ("Spanish Annotation Specialist", None),
        ("AI Training Infrastructure Engineer", "Data Science"),  # a real job, not a gig
        # a Tech word in a non-Tech job
        ("Claims Adjuster - GL & BI", None),
        ("Accounting Administrator", None),
        ("Patent Attorney, Electrical Engineering", None),
        ("Instructional Designer", None),
        ("Senior Civil Site Designer", None),
        ("Real Estate Developer", None),
        ("Product Developer (Footwear)", None),
        ("Head of Product Development", None),
        ("Business Development Manager - Software", None),
        ("Software Sales Executive", None),
        ("VP of Product Marketing", None),
        ("Construction Project Manager", None),
        ("Senior Fraud Researcher", None),
        ("Python Tutor", None),
        ("German Translator", None),
        # Tech-adjacent, but the title alone can't settle it
        ("AI Transformation Strategist", None),
        ("Senior Clinical Data Manager", None),
        ("IT Audit Manager", None),
        ("GTM Engineer", None),
        ("Field Service Engineer", None),
        # no Tech word at all
        ("Medical Coder III", None),
        ("Registered Nurse - Telehealth", None),
        ("Account Executive, Mid-Market", None),
    ],
)
def test_tech_category(title, expected):
    assert tech_category(title) == expected


def test_missing_title_and_extra_spaces():
    assert tech_category(None) is None
    assert tech_category("") is None
    assert tech_category("  Machine   Learning\nEngineer ") == "Data Science"


def test_christian_is_not_hris():
    assert tech_category("Christian Ministry Coordinator") is None


def test_every_category_maps_to_an_industry():
    # Silver maps the answer through industries.csv like a Himalayas parent category, so each needs an industry there.
    with open(INDUSTRIES_CSV, encoding="utf-8", newline="") as file:
        himalayas = {row["raw_value"]: row["industry"] for row in csv.DictReader(file) if row["source"] == "himalayas"}

    assert {category: himalayas.get(category) for category in TECH_CATEGORIES} == {
        "Developer": "Software Engineering",
        "Data Science": "Data Science & Analytics",
        "Product": "Product & Operations",
        "Design": "Web, UI & UX Design",
        "Hardware Engineer": "Hardware & Electronics",
        "Research & Development": "Research & Science",
    }
