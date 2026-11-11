"""Pure scoring functions. No LLM, no I/O, so they are fast and fully unit-testable."""

from . import config
from .models import (
    CATEGORIES,
    CategoryResult,
    EvaluationResult,
    HRCriteria,
    Judgement,
    Requirement,
    ScoredItem,
    Status,
    Verdict,
)


def item_score(status: Status) -> float:
    return config.STATUS_SCORE[status]


def make_scored_item(
    requirement: Requirement,
    judgement: Judgement,
    evidence_verified: bool = True,
    downgraded: bool = False,
) -> ScoredItem:
    """Combine a requirement with the (verified) judgement for it."""
    return ScoredItem(
        requirement=requirement,
        status=judgement.status,
        evidence=judgement.evidence,
        reasoning=judgement.reasoning,
        confidence=judgement.confidence,
        evidence_verified=evidence_verified,
        downgraded=downgraded,
        score=item_score(judgement.status),
    )


def category_percent(items: list[ScoredItem]) -> float:
    """Weighted average of item scores, 0-100, using each requirement's weight."""
    total_weight = sum(i.requirement.weight for i in items)
    if total_weight == 0:
        return 0.0
    return 100 * sum(i.requirement.weight * i.score for i in items) / total_weight


def build_category_results(items: list[ScoredItem]) -> list[CategoryResult]:
    """Group items by category. Categories HR left empty are omitted."""
    results = []
    for category in CATEGORIES:
        cat_items = [i for i in items if i.requirement.category == category]
        if cat_items:
            results.append(
                CategoryResult(
                    category=category,
                    percent=category_percent(cat_items),
                    items=cat_items,
                )
            )
    return results


def overall_percent(results: list[CategoryResult], weights: dict[str, int]) -> float:
    """Weighted average of category percents.

    Only categories HR actually populated take part, and their weights are renormalised.
    If those categories all have weight 0, fall back to equal weights.
    """
    if not results:
        return 0.0
    present = {r.category: weights.get(r.category, 0) for r in results}
    total = sum(present.values())
    if total == 0:
        present = {r.category: 1 for r in results}
        total = len(results)
    return sum(r.percent * present[r.category] for r in results) / total


def missing_must_haves(items: list[ScoredItem]) -> list[str]:
    """Descriptions of must-have requirements that were not met at all (partial does not count)."""
    return [i.requirement.description for i in items if i.requirement.must_have and i.status == "not_met"]


def verdict(percent: float, missing: list[str]) -> Verdict:
    if missing:
        return "Not a match"
    if percent >= config.STRONG_THRESHOLD:
        return "Strong match"
    if percent >= config.PARTIAL_THRESHOLD:
        return "Partial match"
    return "Weak match"


def build_result(
    criteria: HRCriteria,
    items: list[ScoredItem],
    total_years: float,
    warnings: list[str] | None = None,
) -> EvaluationResult:
    """Assemble the final EvaluationResult from scored items."""
    warnings = list(warnings or [])
    categories = build_category_results(items)
    percent = overall_percent(categories, criteria.category_weights)
    missing = missing_must_haves(items)

    meets_min: bool | None = None
    if criteria.min_total_years is not None:
        meets_min = total_years >= criteria.min_total_years
        if not meets_min:
            warnings.append(
                f"Total experience {total_years:.1f} years is below the required {criteria.min_total_years:g}."
            )

    return EvaluationResult(
        role=criteria.role,
        overall_percent=round(percent, 1),
        verdict=verdict(percent, missing),
        category_results=categories,
        missing_must_haves=missing,
        total_years_experience=total_years,
        meets_min_years=meets_min,
        warnings=warnings,
    )
