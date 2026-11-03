"""Find which skills from the skill list (skills.csv) a job's title and description mention."""

import csv
import hashlib
import json
import re
from pathlib import Path

_TOKEN = re.compile(r"(?:\.?[\w+#]+)+|[^\w\s]")
_END = ""

# --- the job's own sections ------------------------------------------------------------------------------------------
# A posting mixes the job (requirements, responsibilities, nice to have) with text about the employer (about us,
# customers and investors, benefits, privacy and hiring notices). Skills named only in the employer's text aren't asked
# of the candidate, so job_text() keeps the job's lines. Headings are compared lowercased, with straight apostrophes
# and without leading or trailing symbols ("🟩 What's in it for you:" -> "what's in it for you").

_YOU_WILL = r"(?:you'll|you will|you'd|you would)"
_JOB_HEADINGS = [
    # English
    r"(?:key |main |core |primary |your |role |job |the |additional |day-to-day |daily )?"
    r"(?:responsibilities|duties|tasks|accountabilities)",
    r"(?:minimum |basic |preferred |required |desired |additional |bonus |key |your |the |technical |must-have "
    r"|nice-to-have )?(?:qualifications|requirements|skills|experience|competencies|expertise)",
    rf"(?:what|things) {_YOU_WILL} (?:do|own|bring|be doing|need|work on|achieve|build|have|tackle|get to do|learn)",
    r"what (?:we're|we are) (?:looking for|expecting)",
    r"what (?:you|we) need",
    r"what we expect",
    r"what is expected",
    r"what you (?:bring|have|do|will)",
    r"what makes you",
    r"who (?:you are|are you)",
    r"what you are",
    r"about you",
    r"is (?:that|this) you",
    r"are you",
    r"you (?:are|have|will|bring|might be|should have|'ll|'re)",
    r"in this role",
    rf"as an? .+ {_YOU_WILL}",
    r"(?:the )?role",
    r"about (?:the|this|our) (?:role|job|position|opportunity|team)",
    r"(?:role|position|job) (?:overview|summary|description|purpose|responsibilities|requirements|details)",
    r"job description",
    r"description",
    r"overview",
    r"(?:the |an |your )?opportunity",
    r"(?:a )?day (?:to day|in the life)",
    r"your (?:role|mission|profile|impact|skills|experience|background|qualifications|responsibilities|day|tasks"
    r"|toolkit|stack)",
    r"nice[- ]to[- ]haves?",
    r"bonus(?: points)?",
    r"preferred",
    r"required",
    r"must[- ]haves?",
    r"(?:the )?ideal candidate",
    r"ideally",
    r"tech(?:nical)? stack",
    r"(?:our )?stack",
    r"technologies",
    r"tools",
    r"tooling",
    r"education",
    r"what success looks like",
    # German
    r"(?:deine |ihre |eure )?(?:aufgaben|rolle|mission|verantwortung|aufgabenbereich|tätigkeiten|tätigkeit)",
    r"was (?:du|sie) mitbring(?:st|en)",
    r"das bring(?:st du|en sie) mit",
    r"das (?:solltest du|sollten sie) mitbringen",
    r"(?:dein|ihr) profil",
    r"qualifikation(?:en)?",
    r"anforderungen",
    r"das erwartet dich",
    r"was dich erwartet",
    r"wen wir suchen",
    r"was du kannst",
    r"was wir (?:von dir |von ihnen )?erwarten",
    r"(?:stellen)?beschreibung",
    # French
    r"(?:vos |tes )?(?:missions|responsabilités)",
    r"(?:vos|tes) compétences",
    r"profil recherché",
    r"(?:votre|ton) (?:profil|rôle)",
    r"compétences(?: requises)?",
    r"ce que (?:tu feras|vous ferez)",
    r"le poste",
    r"description du poste",
    r"missions principales",
    r"ce que nous recherchons",
    # Dutch
    r"wat ga je doen",
    r"wat je gaat doen",
    r"wat (?:breng je mee|wij vragen|vragen wij)",
    r"wat wij van je vragen",
    r"(?:jouw|je) (?:profiel|rol)",
    r"wie ben (?:jij|je)",
    r"functieomschrijving",
    r"functie-eisen",
    r"taken",
    r"verantwoordelijkheden",
    # Spanish and Portuguese
    r"requisitos",
    r"responsabilidades",
    r"funciones",
    r"atividades",
    r"(?:lo )?qu[eé] (?:harás|haras)",
    r"(?:tu |seu |o )?perfil",
    r"(?:lo )?qu[eé] buscamos",
    r"o que buscamos",
    r"o que (?:você|voce) (?:vai|irá) fazer",
    r"o que esperamos",
    r"deseable",
    r"diferenciais",
    r"qualificações",
    r"conhecimentos",
    r"conocimientos",
]
_COMPANY_HEADINGS = [
    # English
    r"about (?!(?:the|this|our) (?:role|job|position|opportunity|team)\b|you\b).*",
    r"who we are",
    r"(?:our|the) company",
    r"our (?:values|mission|story|culture|benefits|offer|investors|customers)",
    r"why (?:join|work|you|us|we)\b.*",
    r"benefits.*",
    r"perks.*",
    r"(?:what )?we offer.*",
    rf"what {_YOU_WILL} get.*",
    r"compensation.*",
    r"salary.*",
    r"pay (?:range|transparency).*",
    r"total rewards.*",
    r"what's in it for you.*",
    r"(?:interview|hiring|recruitment|application|selection) process.*",
    r"how to apply.*",
    r"next steps",
    r"apply(?: now| here)?",
    r"equal (?:employment )?opportunit.*",
    r".*equal opportunity employer.*",
    r"eeo.*",
    r"diversity.*",
    r"accommodation.*",
    r".*personal data.*",
    r".*privacy.*",
    r"additional information",
    r"disclaimer",
    r"legal.*",
    r".*fraud.*",
    r"li-remote",
    r"join us",
    r"join our team",
    r"culture",
    r"life at .*",
    # the job boards' own footers
    r"find (?:more )?.*jobs in .* on arbeitnow",
    r"originally posted on himalayas",
    # German
    r"über uns",
    r"wer wir sind",
    r"(?:was )?wir bieten.*",
    r"das bieten wir.*",
    r"was wir (?:dir |ihnen )?bieten.*",
    r"unser angebot",
    r"benefits für dich",
    r"warum .*",
    r"personenbezogene daten",
    r"wir freuen uns.*",
    r"über (?:das unternehmen|die firma)",
    # French
    r"(?:nos )?avantages.*",
    r"ce que nous (?:offrons|proposons)",
    r"pourquoi nous rejoindre",
    r"qui sommes-nous",
    r"à propos(?: de nous)?",
    r"données personnelles",
    r"notre data policy",
    # Dutch, Spanish and Portuguese
    r"wat (?:bieden wij|wij bieden)",
    r"wij bieden",
    r"over ons",
    r"datos personales",
    r"(?:qué|que) ofrecemos",
    r"beneficios",
    r"sobre nosotros",
    r"quiénes somos",
    r"benefícios",
    r"sobre (?:nós|a empresa)",
    r"o que oferecemos",
]
# A job heading may go on ("Requirements & skills"); a company heading must match whole.
_JOB_HEADING = re.compile(r"^(?:" + "|".join(_JOB_HEADINGS) + r")\b")
_COMPANY_HEADING = re.compile(r"^(?:" + "|".join(_COMPANY_HEADINGS) + r")$")
_HEADING_EDGES = re.compile(r"^[\W_]+|[^\w)]+$")
_WORD = re.compile(r"[^\W\d_]{3,}")
# Words of a job title that don't name the job, for headings like "About the Quality Assurance Engineer III"
_TITLE_FILLER = {
    "senior", "junior", "lead", "staff", "principal", "remote", "hybrid", "contract", "intern",
    "the", "and", "for", "with", "all",
}
# Words that make a line read like a requirement, in the languages of the feeds
_REQUIREMENT = re.compile(
    r"\b(?:experience[ds]?|proficien\w*|familiar\w*|knowledge|expertise|expert in|skilled|skills?|comfortable"
    r"|hands-on|ability to|understanding of|background in|nice to have|bonus|required|preferred|must|stack|you|your"
    r"|du|dein\w*|erfahrung\w*|kenntnisse|kennst|bringst|beherrschst|idealerweise|umgang"
    r"|vous|votre|tu|ton|tes|expérience|maîtrise|connaissances?"
    r"|je|jij|jouw|ervaring|kennis"
    r"|experiencia|experiência|conocimientos?|conhecimentos?|manejo|dominio|domínio|tus|você)\b",
    re.IGNORECASE,
)
# Lines about the employer, wherever they are: customer and investor lists, offer and applicant-privacy notices
_NOTICE = re.compile(
    r"trusted by|relied (?:up)?on by|loved by|backed by|funded by"
    r"|(?:customers|clients|organi[sz]ations|companies|brands|enterprises|businesses|partners|investors|leaders)"
    r" (?:such as|like|including|include)"
    r"|serves [^.]{0,80}including"
    r"|offers?(?: letters?)? [^.]{0,40}(?:sent|issued|delivered|extended) (?:through|via|using|by)"
    r"|by (?:applying|submitting|clicking)|privacy (?:policy|notice)|personal (?:data|information)"
    r"|process(?:ing)? (?:of )?your (?:personal )?(?:data|information)",
    re.IGNORECASE,
)


def _heading_kind(line: str, title_words: set[str]) -> str | None:
    """"job", "company" or "other" when the line is a section heading, else None."""

    line = line.strip()
    if not 3 <= len(line) <= 60 or line[0] in "-•·*":
        return None
    heading = _HEADING_EDGES.sub("", line.lower().replace("’", "'"))

    if _JOB_HEADING.match(heading) or (
        len(title_words) >= 2 and title_words <= set(_WORD.findall(heading))
    ):
        return "job"
    if _COMPANY_HEADING.match(heading):
        return "company"

    # an unknown heading: a line ending in ":", or a short line of capitalised words
    words = line.rstrip(":").split()
    if line.endswith(":") or (
        len(words) <= 6
        and line[-1] not in ".,;"
        and all(not word[0].isalpha() or word[0].isupper() for word in words)
    ):
        return "other"
    return None


def job_text(text: str | None, title: str | None = None) -> str | None:
    """The lines of a job description that are about the job, for matching skills.

    Each line belongs to the section its last heading opened: a job section (requirements, responsibilities, nice to
    have, the role, ... or a heading naming the job's title), a company section (about us, benefits, privacy, hiring
    process, ...) or a section under an unknown heading. Job sections count whole. Elsewhere notices never count, and:
    - sections under an unknown heading count;
    - company sections count only their requirement-like lines ("experience with", "you", "du", "vous", ...);
    - the lines before the first heading count only when they read like a requirement, unless the posting has no job
      section at all; then they all count.
    """

    if text is None:
        return None
    title_words = set(_WORD.findall((title or "").lower())) - _TITLE_FILLER
    lines = text.split("\n")
    kinds = [_heading_kind(line, title_words) for line in lines]
    has_job_section = "job" in kinds

    kept = []
    section = "intro"
    for line, kind in zip(lines, kinds):
        section = kind or section
        if section == "job":
            kept.append(line)
        elif _NOTICE.search(line):
            continue
        elif (
            section == "other"
            or (section == "intro" and not has_job_section)
            or _REQUIREMENT.search(line)
        ):
            kept.append(line)
    return "\n".join(kept)


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
        """Return one dict per skill mentioned: skill, category, mentions (title + the job's lines of the text, see
        job_text) and in_title."""

        employer = self._employer(company)
        in_text = self._matches(job_text(text, title))
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
        matched text in [brackets] with up to `width` characters on each side, on one line. The text is the job's lines
        (see job_text), the same ones match() reads.
        """

        employer = self._employer(company)
        text = job_text(text, title)
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
