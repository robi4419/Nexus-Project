"""Find which skills from the skill list (skills.csv) a job's title and description mention."""

import csv
import hashlib
import json
import re

# No letter, digit, "_", "+", "#" or "." may touch an alias on the left, and no letter, digit, "_", "+" or "#" on the
# right; a "." on the right only blocks when more letters follow. So "Java" doesn't match in "JavaScript", "JS" not in
# "Node.js", "SQL" not in "MySQL", but "Python." at the end of a sentence still matches.
_BEFORE = r"(?<![\w+#.])"
_AFTER = r"(?![\w+#]|\.\w)"


def _phrase_pattern(phrases: list[str], case_sensitive: bool) -> re.Pattern | None:
    """One regex that finds any of the phrases as whole words, trying longer phrases first; None if there are none."""
    if not phrases:
        return None
    alternatives = [
        r"\s+".join(re.escape(word) for word in phrase.split())  # a space in a phrase matches any whitespace
        for phrase in sorted(phrases, key=len, reverse=True)
    ]
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(_BEFORE + "(?:" + "|".join(alternatives) + ")" + _AFTER, flags)


def _blank(exclusions: re.Pattern | None, text: str) -> str:
    """The text with each exclusion phrase replaced by as many spaces, so every position still matches the original."""
    if exclusions is None:
        return text
    return exclusions.sub(lambda found: " " * len(found.group()), text)


def _count(pattern: re.Pattern, exclusions: re.Pattern | None, text: str | None) -> int:
    """How often the pattern occurs in the text after the exclusion phrases are blanked out."""
    if not text:
        return 0
    return len(pattern.findall(_blank(exclusions, text)))


class SkillMatcher:
    """Matches every skill of a skill list (rows with skill, category, aliases, case_sensitive) against job text."""

    def __init__(self, rows: list[dict]):
        # Fingerprint of the list's content: the same rows always give the same 12 characters, any change new ones.
        self.taxonomy_version = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:12]
        self._skills = []
        for row in rows:
            case_sensitive = str(row["case_sensitive"]).lower() == "true"
            aliases = row["aliases"].split("|")
            include = [alias for alias in aliases if not alias.startswith("-")]
            exclude = [alias[1:] for alias in aliases if alias.startswith("-")]
            if not include:
                raise ValueError(f"skill {row['skill']!r} has no aliases to search for")
            pattern = _phrase_pattern(include, case_sensitive)
            exclusions = _phrase_pattern(exclude, case_sensitive=False)  # an excluded phrase never counts, in any case
            self._skills.append((row["skill"], row["category"], pattern, exclusions))

    @classmethod
    def from_csv(cls, path) -> "SkillMatcher":
        with open(path, encoding="utf-8", newline="") as file:
            return cls(list(csv.DictReader(file)))

    def _skills_for(self, company: str | None) -> list[tuple]:
        """The skills to look for. A skill that is part of the employer's own name (Grafana at "Grafana Labs") is left
        out: in that posting the word names the employer, not something the job asks for."""
        return [entry for entry in self._skills if not (company and entry[2].search(company))]

    def match(self, title: str | None, text: str | None, company: str | None = None) -> list[dict]:
        """Return one dict per skill mentioned: skill, category, mentions (title + text) and in_title."""
        found = []
        for skill, category, pattern, exclusions in self._skills_for(company):
            in_title = _count(pattern, exclusions, title)
            in_text = _count(pattern, exclusions, text)
            if in_title or in_text:
                found.append(
                    {"skill": skill, "category": category, "mentions": in_title + in_text, "in_title": in_title > 0}
                )
        return found

    def snippets(self, title: str | None, text: str | None, company: str | None = None, width: int = 40) -> list[dict]:
        """For reviewing matches: one dict per counted match with skill, category, field ("title" or "text") and the
        matched text in [brackets] with up to `width` characters on each side, on one line."""
        found = []
        for skill, category, pattern, exclusions in self._skills_for(company):
            for field, value in (("title", title), ("text", text)):
                if not value:
                    continue
                for hit in pattern.finditer(_blank(exclusions, value)):
                    start, end = hit.span()
                    snippet = f"{value[max(0, start - width):start]}[{value[start:end]}]{value[end:end + width]}"
                    found.append(
                        {"skill": skill, "category": category, "field": field, "snippet": " ".join(snippet.split())}
                    )
        return found
