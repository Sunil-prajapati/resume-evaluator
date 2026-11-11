"""All Pydantic models: HR input, extracted resume data, matcher output, final result."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from . import config

Category = Literal["skills", "experience", "projects"]
CATEGORIES: tuple[Category, ...] = ("skills", "experience", "projects")
Status = Literal["met", "partial", "not_met"]
Verdict = Literal["Strong match", "Partial match", "Weak match", "Not a match"]


# --------------------------------------------------------------------------- HR input
class Requirement(BaseModel):
    id: str = ""  # assigned by HRCriteria if left empty, e.g. "skills-1"
    category: Category
    description: str  # "Python", "Built and deployed a REST API"
    must_have: bool = False
    weight: int = Field(default=3, ge=1, le=5)


class HRCriteria(BaseModel):
    role: str
    min_total_years: float | None = None
    category_weights: dict[Category, int] = Field(
        default_factory=lambda: dict(config.DEFAULT_CATEGORY_WEIGHTS)
    )
    requirements: list[Requirement] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate(self):
        # Missing categories count as weight 0; the total must be exactly 100.
        for c in CATEGORIES:
            self.category_weights.setdefault(c, 0)
        if sum(self.category_weights.values()) != 100:
            raise ValueError("category_weights must sum to 100")

        # Assign ids ("skills-1", "skills-2", ...) and make sure they are unique.
        counters: dict[str, int] = {}
        for r in self.requirements:
            if not r.id:
                counters[r.category] = counters.get(r.category, 0) + 1
                r.id = f"{r.category}-{counters[r.category]}"
        ids = [r.id for r in self.requirements]
        if len(ids) != len(set(ids)):
            raise ValueError("requirement ids must be unique")
        return self


# --------------------------------------------------------------------------- Extracted resume data
# Deliberately NOT extracted: name, gender, age, photo, address (see HLD, fairness).
class Job(BaseModel):
    title: str
    company: str
    start: str | None = None  # "YYYY-MM" or "YYYY"
    end: str | None = None  # "YYYY-MM", "YYYY" or "present"
    summary: str = ""


class Project(BaseModel):
    name: str
    description: str
    technologies: list[str] = []


class ResumeData(BaseModel):
    skills: list[str] = []
    jobs: list[Job] = []
    projects: list[Project] = []


# --------------------------------------------------------------------------- Matcher output
class Judgement(BaseModel):
    """What the LLM returns for one requirement."""

    requirement_id: str
    status: Status
    evidence: str = ""  # verbatim quote from the resume
    reasoning: str = ""
    confidence: float = Field(default=0.5, ge=0, le=1)


class JudgementBatch(BaseModel):
    """One LLM response (one category)."""

    judgements: list[Judgement]


class ScoredItem(BaseModel):
    """A judgement after verification and scoring."""

    requirement: Requirement
    status: Status
    evidence: str = ""
    reasoning: str = ""
    confidence: float = 0.5
    evidence_verified: bool = True
    downgraded: bool = False  # True if the verifier changed the status
    score: float  # 0 / 0.5 / 1


class CategoryResult(BaseModel):
    category: Category
    percent: float
    items: list[ScoredItem]


class EvaluationResult(BaseModel):
    role: str
    overall_percent: float
    verdict: Verdict
    category_results: list[CategoryResult]
    missing_must_haves: list[str]
    total_years_experience: float
    meets_min_years: bool | None = None
    warnings: list[str] = []
