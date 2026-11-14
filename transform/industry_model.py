"""The industry model: which industry a job is, learned from hand labels (Phase 5, decision 15).

A logistic regression on a job's title (its words, and groups of letters inside them) and its skills. It learns only
from jobs labelled by hand with docs/industry-labelling-guide.md: no regex decides an industry here.

A job is a dict with "title" (text or None) and "skills" (a list of skill names). Unlike the rest of transform/, this
module needs scikit-learn, so only the notebooks and tests that use the model import it.
"""

import joblib
import numpy as np
import sklearn
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

NOT_CLASSIFIED = "Not classified"

# The guide's industries by group, in the guide's order.
GROUPS = {
    "Software": [
        "Backend", "Frontend", "Full-stack", "Mobile", "Enterprise Applications", "Solutions & Implementation",
        "Software Engineering, general",
    ],
    "Data": ["Data Analytics & BI", "Data Engineering", "Machine Learning & AI"],
    "Infrastructure & Security": ["DevOps, Cloud & SRE", "IT Infrastructure & Administration", "Cybersecurity"],
    "Quality & Support": ["QA & Testing", "Technical Support"],
    "Hardware": ["Hardware & Embedded"],
    "Design": ["UI & UX Design", "Creative & Design"],
    "Product & Projects": ["Product Management", "Project & Program Management"],
    "Business": [
        "Sales & Business Development", "Marketing", "Customer Support & Success", "Finance & Accounting",
        "HR & Recruiting", "Legal & Compliance", "Operations & Management", "Content & Editorial",
        "Admin & Assistance",
    ],
    "Other fields": [
        "Engineering & Manufacturing", "Research & Science", "Healthcare & Medical", "Education & Training",
        "Logistics & Supply Chain",
    ],
    NOT_CLASSIFIED: [NOT_CLASSIFIED],
}
INDUSTRIES = [industry for industries in GROUPS.values() for industry in industries]
GROUP_OF = {industry: group for group, industries in GROUPS.items() for industry in industries}

SKILL_SEPARATOR = "|"
FILE_FORMAT = 1


def unspecified(group: str) -> str:
    """What a job shows when the model is sure of its group but not of its industry: "Software, unspecified"."""
    return f"{group}, unspecified"


def industry_list() -> list[tuple[str, str, int]]:
    """Every value a job's industry can take, as (industry, industry_group, sort_order): the industries group by
    group, then the group's "unspecified" row when it has several industries, and "Not classified" last.
    databricks/reference/industry_list.csv is this list."""
    rows = []
    for group, industries in GROUPS.items():
        names = list(industries)
        if len(industries) > 1:
            names.append(unspecified(group))
        rows += [(name, group) for name in names]
    return [(name, group, order) for order, (name, group) in enumerate(rows, start=1)]


class IndustryModel:
    def __init__(self):
        # the title's words, alone and in pairs
        self.title_words = TfidfVectorizer(
            ngram_range=(1, 2), min_df=1, sublinear_tf=True, token_pattern=r"(?u)[\w+#.]{2,}"
        )
        # groups of 3 to 5 letters inside its words, so "Softwareentwickler" shares pieces with "Entwickler"
        self.title_letters = TfidfVectorizer(
            analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=150_000, sublinear_tf=True
        )
        # the job's skills, each present or absent: the names joined with "|" and split there again
        self.skills = TfidfVectorizer(token_pattern=r"[^|]+", lowercase=False, use_idf=False)
        self.classifier = LogisticRegression(C=20.0, max_iter=500)
        self.classes: list[str] = []
        self.groups: list[str] = []

    def _matrix(self, jobs, fit):
        titles = [job.get("title") or "" for job in jobs]
        skills = [
            SKILL_SEPARATOR.join(skill.replace(SKILL_SEPARATOR, " ") for skill in job.get("skills") or [])
            for job in jobs
        ]
        blocks = [
            (vectorizer.fit_transform if fit else vectorizer.transform)(texts)
            for vectorizer, texts in [(self.title_words, titles), (self.title_letters, titles), (self.skills, skills)]
        ]
        return hstack(blocks).tocsr()

    def _set_classes(self):
        self.classes = list(self.classifier.classes_)
        self.groups = sorted({GROUP_OF[industry] for industry in self.classes})
        # one row per industry, one column per group: 1 where the industry belongs to the group
        self._membership = np.array(
            [[GROUP_OF[industry] == group for group in self.groups] for industry in self.classes], dtype=float
        )

    def fit(self, jobs: list[dict], industries: list[str]) -> "IndustryModel":
        unknown = sorted(set(industries) - set(INDUSTRIES))
        if unknown:
            raise ValueError(f"Not industries of the guide: {unknown}")
        self.classifier.fit(self._matrix(jobs, fit=True), industries)
        self._set_classes()
        return self

    def proba(self, jobs: list[dict]) -> np.ndarray:
        """One row per job, one column per industry in self.classes."""
        if not jobs:
            return np.zeros((0, len(self.classes)))
        return np.vstack(
            [
                self.classifier.predict_proba(self._matrix(jobs[start:start + 5000], fit=False))
                for start in range(0, len(jobs), 5000)
            ]
        )

    def predict(self, jobs: list[dict]) -> list[tuple[str, float, str, float]]:
        """Per job: (industry, its probability, group, the group's probability). A group's probability is the sum
        over its industries, so the model can be sure of "Software" while unsure between Backend and Full-stack."""
        proba = self.proba(jobs)
        by_group = proba @ self._membership
        best, best_group = proba.argmax(axis=1), by_group.argmax(axis=1)
        return [
            (self.classes[i], float(proba[row, i]), self.groups[g], float(by_group[row, g]))
            for row, (i, g) in enumerate(zip(best, best_group))
        ]

    def save(self, path: str) -> None:
        """Write the fitted parts as plain scikit-learn objects, so a later change to this class can't break loading."""
        joblib.dump(
            {
                "format": FILE_FORMAT,
                "sklearn_version": sklearn.__version__,
                "title_words": self.title_words,
                "title_letters": self.title_letters,
                "skills": self.skills,
                "classifier": self.classifier,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "IndustryModel":
        saved = joblib.load(path)
        if saved["format"] != FILE_FORMAT:
            raise ValueError(f"Model file format {saved['format']}, expected {FILE_FORMAT}")
        if saved["sklearn_version"] != sklearn.__version__:
            # A fitted object read by another scikit-learn version can give different answers without any error.
            raise ValueError(
                f"The model was saved with scikit-learn {saved['sklearn_version']}, but {sklearn.__version__} is "
                "installed. Install the saved version, or train the model again."
            )
        model = cls()
        model.title_words, model.title_letters = saved["title_words"], saved["title_letters"]
        model.skills, model.classifier = saved["skills"], saved["classifier"]
        model._set_classes()
        return model


def score(predictions: list[tuple[str, float, str, float]], acceptable: list[list[str]], sure: float) -> dict:
    """How well predictions match hand labels. `acceptable` lists, per job, the best industry first and then any
    others the guide also accepts. Shares are between 0 and 1.
    - industry_right: the industry is one of the acceptable ones;
    - best_right: it is the best one;
    - answered: the industry's probability is at least `sure`;
    - right_when_answered: industry_right among the answered jobs;
    - group_right, group_answered, group_right_when_answered: the same for the group of the best industry."""
    jobs = len(predictions)
    if jobs == 0 or jobs != len(acceptable):
        raise ValueError("score needs one list of acceptable industries per prediction, and at least one")
    right = [industry in ok for (industry, *_), ok in zip(predictions, acceptable)]
    best = [industry == ok[0] for (industry, *_), ok in zip(predictions, acceptable)]
    group_right = [group == GROUP_OF[ok[0]] for (_, _, group, _), ok in zip(predictions, acceptable)]
    answered = [probability >= sure for _, probability, _, _ in predictions]
    group_answered = [probability >= sure for *_, probability in predictions]
    return {
        "jobs": jobs,
        "industry_right": sum(right) / jobs,
        "best_right": sum(best) / jobs,
        "answered": sum(answered) / jobs,
        "right_when_answered": sum(r for r, a in zip(right, answered) if a) / max(sum(answered), 1),
        "group_right": sum(group_right) / jobs,
        "group_answered": sum(group_answered) / jobs,
        "group_right_when_answered": sum(r for r, a in zip(group_right, group_answered) if a)
        / max(sum(group_answered), 1),
    }
