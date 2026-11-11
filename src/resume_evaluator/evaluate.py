"""The whole pipeline as one function of (resume, criteria). Phase 6's CLI is a thin shell around it."""

from datetime import date
from pathlib import Path

from .extractor import extract_resume, total_years
from .matcher import match
from .models import EvaluationResult, HRCriteria
from .parser import extract_text
from .scoring import build_result, make_scored_item
from .verifier import verify


def evaluate_text(
    resume_text: str,
    criteria: HRCriteria,
    *,
    today: date | None = None,
    debug: bool = False,
    **llm_kwargs,
) -> EvaluationResult:
    """parse-free pipeline: extract -> years -> match -> verify -> score. 1 + (non-empty categories) LLM calls."""
    resume = extract_resume(resume_text, debug=debug, **llm_kwargs)
    years, warnings = total_years(resume.jobs, today)

    judgements, match_warnings = match(criteria, resume_text, resume, years, debug=debug, **llm_kwargs)
    warnings += match_warnings

    requirements = {r.id: r for r in criteria.requirements}
    items = []
    for raw in judgements:
        req = requirements[raw.requirement_id]
        checked, verified, downgraded = verify(raw, resume_text)
        if downgraded:
            warnings.append(f"Downgraded '{req.description}' from {raw.status} to not_met: evidence not verified in the resume.")
        items.append(make_scored_item(req, checked, evidence_verified=verified, downgraded=downgraded))

    return build_result(criteria, items, years, warnings)


def evaluate_file(path: str | Path, criteria: HRCriteria, **kwargs) -> EvaluationResult:
    return evaluate_text(extract_text(path), criteria, **kwargs)
