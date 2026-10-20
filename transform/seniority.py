"""Derive a job's seniority from its title, falling back to the level the source gave."""

import re

# Phrases that contain a seniority word without meaning that seniority; removed before the rules run.
_TRAPS = re.compile(
    r"\b(?:lead gen(?:eration)?|staff accountant|member of technical staff|clinical research associate"
    r"|office of the [\w.-]+|assistant to the [\w.-]+)\b",
    re.IGNORECASE,
)

# Checked in this order and the first match wins, so "Associate Director" is Director and "Sr. Staff" is Lead.
_RULES = [
    (level, re.compile(rf"\b(?:{words})\b", re.IGNORECASE))
    for level, words in [
        ("Executive", r"chief|ceo|cto|cfo|coo|cio|ciso|vp|svp|evp|president"),
        ("Director", r"director|head of"),
        ("Lead", r"lead|principal|staff"),
        ("Senior", r"senior|sr|snr"),
        ("Mid", r"mid[- ]?level|intermediate"),
        ("Junior", r"junior|jr|entry[- ]level|early[- ]career|graduate|new grad|associate"),
        ("Intern", r"interns?|internship|trainee|apprentice|apprenticeship"),
    ]
]

# Jobicy's jobLevel values we trust; its "Director" and "Any" are unreliable, so they become Unspecified.
_SOURCE_LEVELS = {"senior": "Senior", "midweight": "Mid", "entry-level, junior": "Junior"}


def seniority(title: str | None, source_level: str | None) -> tuple[str, str]:
    """Return (seniority, seniority_source), where seniority_source is "title", "source_level" or "none"."""
    cleaned = _TRAPS.sub(" ", title or "")
    for level, pattern in _RULES:
        if pattern.search(cleaned):
            return level, "title"
    level = _SOURCE_LEVELS.get((source_level or "").strip().lower())
    if level:
        return level, "source_level"
    return "Unspecified", "none"
