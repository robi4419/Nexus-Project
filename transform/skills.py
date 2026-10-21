"""Find which skills from the skill list (skills.csv) a job's title and description mention."""

import csv
import hashlib
import json
import re
from pathlib import Path

# No letter, digit, "_", "+", "#" or "." may touch an alias on the left, and no letter, digit, "_", "+" or "#" on the
# right; a "." on the right only blocks when more letters follow. So "Java" doesn't match in "JavaScript", "JS" not in
# "Node.js", "SQL" not in "MySQL", but "Python." at the end of a sentence still matches.
_BEFORE = r"(?<![\w+#.])"
_AFTER = r"(?![\w+#]|\.\w)"

# A word for the prefilter: a run of letters or digits in any alphabet ("node" and "js" in "Node.js").
_WORD = re.compile(r"[^\W_]+")


def _fingerprint(*parts: str) -> str:
    """12 characters that change whenever any of the parts change."""
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:12]


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


def _anchors(aliases: list[str]) -> frozenset[str] | None:
    """The first word of each alias, lowercased ("Node.js" -> "node", ".NET" -> "net", "C++" -> "c"). An alias can only
    match where its first word stands as a whole word in the text. None (always search) if an alias has no word."""
    first_words = [_WORD.findall(alias.lower())[:1] for alias in aliases]
    return None if [] in first_words else frozenset(words[0] for words in first_words)


def _words(*texts: str | None) -> set[str]:
    """Every word of the texts, lowercased, for the prefilter."""
    return set(_WORD.findall(" ".join(text for text in texts if text).lower()))


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
        self.taxonomy_version = _fingerprint(json.dumps(rows, sort_keys=True))
        # Fingerprint of the list and of this file's code, for caching results: a rule change re-matches everything.
        code = Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
        self.matcher_version = _fingerprint(self.taxonomy_version, code)
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
            self._skills.append((row["skill"], row["category"], pattern, exclusions, _anchors(include)))

    @classmethod
    def from_csv(cls, path) -> "SkillMatcher":
        with open(path, encoding="utf-8", newline="") as file:
            return cls(list(csv.DictReader(file)))

    def _candidates(self, title: str | None, text: str | None, company: str | None, prefilter: bool) -> list[tuple]:
        """The skills worth searching for.
        - A skill that is part of the employer's own name (Grafana at "Grafana Labs") is left out: in that posting the
          word names the employer, not something the job asks for.
        - With the prefilter, a skill is left out when none of its aliases' first words occurs in the texts. That only
          skips searches that couldn't find anything, so results never change; it makes matching about 10x faster."""
        words = _words(title, text) if prefilter else None
        return [
            entry
            for entry in self._skills
            if not (company and entry[2].search(company))
            and (words is None or entry[4] is None or not entry[4].isdisjoint(words))
        ]

    def match(
        self, title: str | None, text: str | None, company: str | None = None, *, prefilter: bool = True
    ) -> list[dict]:
        """Return one dict per skill mentioned: skill, category, mentions (title + text) and in_title."""
        found = []
        for skill, category, pattern, exclusions, _ in self._candidates(title, text, company, prefilter):
            in_title = _count(pattern, exclusions, title)
            in_text = _count(pattern, exclusions, text)
            if in_title or in_text:
                found.append(
                    {"skill": skill, "category": category, "mentions": in_title + in_text, "in_title": in_title > 0}
                )
        return found

    def snippets(
        self, title: str | None, text: str | None, company: str | None = None, width: int = 40, *, prefilter: bool = True
    ) -> list[dict]:
        """For reviewing matches: one dict per counted match with skill, category, field ("title" or "text") and the
        matched text in [brackets] with up to `width` characters on each side, on one line."""
        found = []
        for skill, category, pattern, exclusions, _ in self._candidates(title, text, company, prefilter):
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
