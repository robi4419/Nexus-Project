import csv
from pathlib import Path

import pytest

from transform.seniority import LEVELS, seniority

LEVELS_CSV = Path(__file__).parent.parent / "databricks" / "reference" / "levels.csv"


# The second value is the fallback level: the source's own level after mapping through levels.csv (None if unmapped).
@pytest.mark.parametrize(
    ("title", "fallback_level", "expected"),
    [
        # one or more titles per rule (real Jobicy titles where possible)
        ("Chief Technology Officer", None, ("Executive", "title")),
        ("Regional VP, Sales", None, ("Executive", "title")),
        ("SVP of Engineering", None, ("Executive", "title")),
        ("Vice President, Partnership Sales", None, ("Executive", "title")),
        ("President - Business Unit", None, ("Executive", "title")),
        ("Head of Engineering", None, ("Director", "title")),
        ("Team Lead Software Engineer", "Senior", ("Lead", "title")),
        ("Customer Care Team Leader", None, ("Lead", "title")),
        ("Principal Product Manager", "Senior", ("Lead", "title")),
        ("Staff Data Engineer", None, ("Lead", "title")),
        ("SecOps Security Engineer (Staff-level, L6)", "Senior", ("Lead", "title")),
        ("Sr. Software Engineer, Cloud Platform", "Senior", ("Senior", "title")),
        ("Senior Account Executive, Enterprise", None, ("Senior", "title")),
        ("SENIOR DATA ENGINEER", None, ("Senior", "title")),
        ("Intermediate Data Analyst", None, ("Mid", "title")),
        ("Junior QA Engineer - US Remote", "Senior", ("Junior", "title")),
        ("Entry-level communications specialist", "Junior", ("Junior", "title")),
        ("Graduate HR Generalist - APAC", "Junior", ("Junior", "title")),
        ("New Grad Software Engineer", None, ("Junior", "title")),
        ("Software Engineer, Early Career", None, ("Junior", "title")),
        ("Customer Success Associate", None, ("Junior", "title")),
        ("Applied Scientist Intern", "Junior", ("Intern", "title")),
        ("Data Engineering Apprentice", None, ("Intern", "title")),
        # rule order: the first match wins
        ("Associate Director, Tax", None, ("Director", "title")),
        ("Sr. Director, Renewals Operations", None, ("Director", "title")),
        ("Sr. Staff Machine Learning Systems Engineer", "Senior", ("Lead", "title")),
        ("Senior / Staff Threat Intelligence Analyst, Hacks", None, ("Lead", "title")),
        ("Mid/Sr. Product Engineer, Intelligence", "Senior", ("Senior", "title")),
        ("Business Development Manager (Junior to Mid-Level) – Hong Kong", "Senior", ("Mid", "title")),
        # traps: a seniority word that doesn't mean seniority
        ("Executive Assistant to the CEO", None, ("Unspecified", "none")),
        ("Principal Engineer (AI, Office of the CEO)", None, ("Lead", "title")),
        ("Senior Staff Operations Manager, Office of the President (PED)", None, ("Lead", "title")),
        ("Member of Technical Staff (ML)", "Senior", ("Senior", "source_level")),
        ("Clinical Research Associate", "Mid", ("Mid", "source_level")),
        ("Sr Clinical Research Associate (Serbia)", "Senior", ("Senior", "title")),
        ("Lead Generation Specialist", None, ("Unspecified", "none")),
        ("Staff Accountant", "Mid", ("Mid", "source_level")),
        ("Senior Staff Accountant", None, ("Senior", "title")),
        ("Account Executive II, Mid-Market", None, ("Unspecified", "none")),
        ("CRO Specialist", None, ("Unspecified", "none")),
        ("Internal Auditor", None, ("Unspecified", "none")),
        ("Leadership Development Partner", "Mid", ("Mid", "source_level")),
        # German, French and Dutch titles (many from the 2026-10-20 Arbeitnow sample)
        ("Geschäftsführer (m/w/d)", None, ("Executive", "title")),
        ("Directeur Général Adjoint", None, ("Executive", "title")),
        ("IT-Leiter (m/w/d)", None, ("Director", "title")),
        ("Leiter/in Technik und Unterhalt (Schwerpunkt Elektro-/Steuerungstechnik)", None, ("Director", "title")),
        ("Abteilungsleiter Finanzen", None, ("Director", "title")),
        ("Directeur Marketing (H/F)", None, ("Director", "title")),
        ("Teamleiter:in SAP", None, ("Lead", "title")),
        ("Team-Leiter Kundenservice (w/m/d)", None, ("Lead", "title")),
        ("Gruppenleiter Entwicklung", None, ("Lead", "title")),
        ("Chef d'équipe logistique (H/F)", None, ("Lead", "title")),
        ("Teamleider Klantenservice", None, ("Lead", "title")),
        ("Medior Developer", None, ("Mid", "title")),
        ("Berufseinsteiger Vertrieb (m/w/d)", None, ("Junior", "title")),
        ("Absolvent:in Data Science", None, ("Junior", "title")),
        ("Werkstudent (m/w/d) Robotik-Projektmanagement & Implementierung", None, ("Intern", "title")),
        ("Praktikant:in Marketing", None, ("Intern", "title")),
        ("Ausbildung zum Fachinformatiker (m/w/d)", None, ("Intern", "title")),
        ("Duales Studium Informatik", None, ("Intern", "title")),
        ("Stage Finance | Amsterdam hbo/wo", None, ("Intern", "title")),
        ("Stagiaire Opérations Titres (f/h/d)", None, ("Intern", "title")),
        ("Alternance - Chargé de communication", None, ("Intern", "title")),
        # German, French and English traps
        ("Projektleiter (m/w/d) Anlagen- & Rohrleitungsbau - Wasseraufbereitung", None, ("Unspecified", "none")),
        ("Projektleiter:in Umwelt", "Mid", ("Mid", "source_level")),
        ("Bauleiter Hochbau (m/w/d)", None, ("Unspecified", "none")),
        ("Ausbildungsleiter (m/w/d)", None, ("Unspecified", "none")),
        ("Vorstandsassistenz (m/w/d)", None, ("Unspecified", "none")),
        ("Stage Manager", None, ("Unspecified", "none")),
        ("Early-Stage Investor", None, ("Unspecified", "none")),
        # no title rule: the fallback level, if it is one of ours
        ("Product Manager", "Senior", ("Senior", "source_level")),
        ("Data Analyst", "Mid", ("Mid", "source_level")),
        ("Data Analyst", "Junior", ("Junior", "source_level")),
        ("Data Analyst", "Director", ("Director", "source_level")),
        ("Data Analyst", None, ("Unspecified", "none")),
        ("Data Analyst", "Midweight", ("Unspecified", "none")),  # a raw source value is ignored, not guessed
    ],
)
def test_seniority(title, fallback_level, expected):
    assert seniority(title, fallback_level) == expected


def test_missing_values():
    assert seniority(None, None) == ("Unspecified", "none")
    assert seniority(None, "Senior") == ("Senior", "source_level")
    assert seniority("Staff Data Engineer", None) == ("Lead", "title")


def test_levels_are_ordered_lowest_to_highest():
    assert LEVELS == ("Intern", "Junior", "Mid", "Senior", "Lead", "Director", "Executive")


def test_levels_csv_maps_jobicy_like_phase_2():
    # Phase 2 trusted Jobicy's Senior, Midweight and Entry-Level/Junior, and ignored its Director and Any.
    with open(LEVELS_CSV, encoding="utf-8", newline="") as file:
        jobicy = {row["raw_value"]: row["seniority"] or None for row in csv.DictReader(file) if row["source"] == "jobicy"}

    assert jobicy == {"Senior": "Senior", "Midweight": "Mid", "Entry-Level, Junior": "Junior", "Director": None, "Any": None}