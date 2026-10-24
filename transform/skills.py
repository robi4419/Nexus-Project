"""Find which skills from the skill list (skills.csv) a job's title and description mention."""

import csv
import hashlib
import json
import re
from pathlib import Path

_TOKEN = re.compile(r"(?:\.?[\w+#]+)+|[^\w\s]")
_END = ""


def _fingerprint(*parts: str) -> str:
    """12 characters that change whenever any of the parts change."""
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:12]


class SkillMatcher:
    """Matches every skill of a skill list (rows with skill, category, aliases, case_sensitive) against job text."""

    @staticmethod
    def _tokenize(text: str) -> list[tuple]:
        return [
            (match.group(), match.start(), match.end())
            for match in _TOKEN.finditer(text)
        ]

    def __init__(self, rows: list[dict]):
        # Fingerprint of the list's content: the same rows always give the same 12 characters, any change new ones.
        self.taxonomy_version = _fingerprint(json.dumps(rows, sort_keys=True))

        # Fingerprint of the list and of this file's code, for caching results: a rule change re-matches everything.
        code = Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")
        self.matcher_version = _fingerprint(self.taxonomy_version, code)

        self._skills = []
        self._trie = {}

        for index, row in enumerate(rows):
            self._skills.append((row["skill"], row["category"]))

            case_sensitive = str(row["case_sensitive"]).lower() == "true"
            aliases = row["aliases"].split("|")
            include = [alias for alias in aliases if not alias.startswith("-")]
            exclude = [alias[1:] for alias in aliases if alias.startswith("-")]
            if not include:
                raise ValueError(f"skill {row['skill']!r} has no aliases to search for")

            include_aliases_tokens = [
                (self._tokenize(alias), False) for alias in include
            ]
            exclude_aliases_tokens = [
                (self._tokenize(alias), True) for alias in exclude
            ]

            for alias_tokens, is_exclusion in (
                include_aliases_tokens + exclude_aliases_tokens
            ):
                node = self._trie
                case_tokens = []
                for text, *_ in alias_tokens:
                    node = node.setdefault(text.lower(), {})
                    if case_sensitive and not is_exclusion:
                        case_tokens.append(text)

                node.setdefault(_END, []).append(
                    (
                        index,
                        is_exclusion,
                        (
                            tuple(case_tokens)
                            if case_sensitive and not is_exclusion
                            else None
                        ),
                    )
                )

    @classmethod
    def from_csv(cls, path) -> "SkillMatcher":
        with open(path, encoding="utf-8", newline="") as file:
            return cls(list(csv.DictReader(file)))

    def _find(self, tokens: list[tuple]) -> list[tuple]:
        """Every alias and exclusion phrase found in the tokens, as (first token, end token, skill index, is_exclusion)."""

        hits = []
        lower = [text.lower() for text, *_ in tokens]

        for i in range(len(tokens)):
            node = self._trie.get(lower[i])
            j = i + 1
            while node is not None:
                for index, is_exclusion, case_tokens in node.get(_END, ()):
                    if (
                        case_tokens is None
                        or tuple(text for text, *_ in tokens[i:j]) == case_tokens
                    ):
                        hits.append((i, j, index, is_exclusion))

                if j == len(tokens):
                    break
                node = node.get(lower[j])
                j += 1

        return hits

    def _matches(self, text: str | None) -> dict[int, list[tuple[int, int]]]:
        """Per skill index: the character spans of its counted matches,
        leftmost-longest and not overlapping its own exclusions."""

        if text is None or text.strip() == "":
            return {}
        tokens = self._tokenize(text)
        hits = self._find(tokens)

        found = {}
        blocked = {}
        for i, j, index, is_exclusion in hits:
            if is_exclusion:
                blocked.setdefault(index, []).append((i, j))
            else:
                found.setdefault(index, []).append((i, j))

        skills = {}
        for skill_index, spans in found.items():
            blocked_spans = blocked.get(skill_index, ())
            non_blocked_spans = []
            for i, j in spans:
                if not any(
                    i < block_end and block_start < j
                    for block_start, block_end in blocked_spans
                ):
                    non_blocked_spans.append((i, j))

            non_blocked_spans.sort(key=lambda span: (span[0], -span[1]))
            last_kept_span_end = 0
            for i, j in non_blocked_spans:
                if i >= last_kept_span_end:
                    skills.setdefault(skill_index, []).append(
                        (tokens[i][1], tokens[j - 1][2])
                    )
                    last_kept_span_end = j

        return skills

    def _employer(self, company: str | None) -> set[int]:
        """The indexes of the skills named in the company name;
        their matches in the posting are about the employer, not requirements."""

        return set(self._matches(company))

    def match(
        self,
        title: str | None,
        text: str | None,
        company: str | None = None,
    ) -> list[dict]:
        """Return one dict per skill mentioned: skill, category, mentions (title + text) and in_title."""

        employer = self._employer(company)
        in_text = self._matches(text)
        in_title = self._matches(title)

        skills_indexes = (set(in_text) | set(in_title)) - employer
        skills = []
        for skill_index in sorted(skills_indexes):
            skill, category = self._skills[skill_index]
            mentions_in_title = len(in_title.get(skill_index, ()))
            mentions_in_text = len(in_text.get(skill_index, ()))

            skills.append(
                {
                    "skill": skill,
                    "category": category,
                    "mentions": mentions_in_title + mentions_in_text,
                    "in_title": skill_index in in_title,
                }
            )

        return skills

    def snippets(
        self,
        title: str | None,
        text: str | None,
        company: str | None = None,
        width: int = 40,
    ) -> list[dict]:
        """For reviewing matches: one dict per counted match with skill, category, field ("title" or "text") and the
        matched text in [brackets] with up to `width` characters on each side, on one line.
        """

        employer = self._employer(company)
        in_text = self._matches(text)
        in_title = self._matches(title)

        skills_indexes = (set(in_text) | set(in_title)) - employer
        snippets = []
        for skill_index in sorted(skills_indexes):
            skill, category = self._skills[skill_index]

            for field, value, spans in (
                ("title", title, in_title),
                ("text", text, in_text),
            ):
                for start, end in spans.get(skill_index, ()):
                    # max(0, ...): near the start of the text, a negative index would count from the end instead
                    before = value[max(0, start - width) : start]
                    after = value[end : end + width]
                    snippet = f"{before}[{value[start:end]}]{after}"

                    snippets.append(
                        {
                            "skill": skill,
                            "category": category,
                            "field": field,
                            "snippet": " ".join(snippet.split()),
                        }
                    )

        return snippets
