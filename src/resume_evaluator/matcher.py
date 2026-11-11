"""Judge each HR requirement against the resume: one LLM call per category."""

from .llm import call_structured
from .models import CATEGORIES, HRCriteria, Judgement, JudgementBatch, Requirement, ResumeData
from .prompts import MATCH_SYSTEM, build_match_user


def reconcile(requirements: list[Requirement], judgements: list[Judgement]) -> tuple[list[Judgement], list[str]]:
    """Return exactly one judgement per requirement, in requirement order.

    The model sometimes omits, duplicates or invents ids. Unknown and duplicate ids are dropped
    (first wins) and omitted requirements become "not_met" with a warning.
    """
    wanted = {r.id for r in requirements}
    by_id: dict[str, Judgement] = {}
    for j in judgements:
        if j.requirement_id in wanted and j.requirement_id not in by_id:
            by_id[j.requirement_id] = j

    result, warnings = [], []
    for r in requirements:
        if r.id in by_id:
            result.append(by_id[r.id])
        else:
            result.append(
                Judgement(requirement_id=r.id, status="not_met", reasoning="not returned by model", confidence=0.0)
            )
            warnings.append(f"The model returned no judgement for '{r.description}'; counted as not met.")
    return result, warnings


def match(
    criteria: HRCriteria,
    resume_text: str,
    resume: ResumeData,
    total_years: float,
    *,
    debug: bool = False,
    **llm_kwargs,
) -> tuple[list[Judgement], list[str]]:
    """One LLM call per non-empty category. Returns (judgements in criteria order, warnings)."""
    extracted_json = resume.model_dump_json(indent=2)
    judgements: list[Judgement] = []
    warnings: list[str] = []
    for category in CATEGORIES:
        reqs = [r for r in criteria.requirements if r.category == category]
        if not reqs:
            continue
        payload = [{"id": r.id, "description": r.description, "must_have": r.must_have} for r in reqs]
        user = build_match_user(payload, resume_text, extracted_json, total_years)
        batch = call_structured(MATCH_SYSTEM, user, JudgementBatch, debug=debug, **llm_kwargs)
        got, notes = reconcile(reqs, batch.judgements)
        judgements += got
        warnings += notes
    return judgements, warnings
