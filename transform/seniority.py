"""Derive a job's seniority from its title, falling back to a level the source gave (already mapped to ours)."""

import re

# Our seniority levels, lowest to highest.
LEVELS = ("Intern", "Junior", "Mid", "Senior", "Lead", "Director", "Executive")

# Phrases that contain a seniority word without meaning that seniority; removed before the rules run. The German job
# names "Projektleiter" (project manager) and "Bauleiter" (site manager) end in "-leiter" but, like "Project Manager",
# say nothing about level; "early-stage" and "Stage Manager" are English, not the French/Dutch "stage" (internship).
_TRAPS = re.compile(
    r"\b(?:lead gen(?:eration)?|staff accountant|member of technical staff|clinical research associate"
    r"|office of the [\w.-]+|assistant to the [\w.-]+"
    r"|projektleit\w*|bauleit\w*"
    r"|(?:early|late|growth|seed|multi)[- ]stage|stage manager|stage technician)\b",
    re.IGNORECASE,
)

# Checked in this order and the first match wins, so "Associate Director" is Director and "Sr. Staff" is Lead.
# Each level lists English words first, then German, French and Dutch ones. German team-lead words come before
# Director because "Team-Leiter" contains "Leiter" (head, a Director word).
_RULES = [
    (level, re.compile(rf"\b(?:{words})\b", re.IGNORECASE))
    for level, words in [
        ("Executive", r"chief|ceo|cto|cfo|coo|cio|ciso|vp|svp|evp|president"
                      r"|geschäftsführ(?:er|erin|ung)|vorstand"
                      r"|directeur général|directrice générale|pdg"),
        ("Lead", r"team[- ]?leit\w*|gruppenleit\w*|schichtleit\w*|teamlead|chef d['’]équipe|teamleider"),
        ("Director", r"director|head of"
                     r"|leiter(?:in)?|leitung|abteilungsleit\w*|bereichsleit\w*|niederlassungsleit\w*"
                     r"|vertriebsleit\w*|standortleit\w*|direktor(?:in)?"
                     r"|directeur|directrice"),
        ("Lead", r"lead|team leader|principal|staff"),
        ("Senior", r"senior|sr|snr"),
        ("Mid", r"mid[- ]?level|intermediate|medior"),
        ("Junior", r"junior|jr|entry[- ]level|early[- ]career|graduate|new grad|associate"
                   r"|berufseinsteiger(?:in)?|absolvent(?:in)?|débutante?|jeune diplômée?"),
        ("Intern", r"interns?|internship|trainee|apprentice|apprenticeship"
                   r"|praktikum|praktikant\w*|werkstudent\w*|ausbildung|auszubildende[rn]?|azubi"
                   r"|duales studium|dualer student"
                   r"|stage|stagiaire|alternance|alternante?|apprentie?|stagiair"),
    ]
]


def seniority(title: str | None, fallback_level: str | None) -> tuple[str, str]:
    """Return (seniority, seniority_source).
    - "title": the first title rule that matches.
    - "source_level": otherwise the fallback, i.e. the source's own level after mapping through levels.csv
      (only one of LEVELS counts; anything else is ignored).
    - "none": otherwise "Unspecified"."""
    cleaned = _TRAPS.sub(" ", title or "")
    for level, pattern in _RULES:
        if pattern.search(cleaned):
            return level, "title"
    if fallback_level in LEVELS:
        return fallback_level, "source_level"
    return "Unspecified", "none"
