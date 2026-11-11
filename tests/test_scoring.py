import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from resume_evaluator.models import HRCriteria, Judgement, Requirement
from resume_evaluator.scoring import (
    build_category_results,
    build_result,
    category_percent,
    make_scored_item,
    overall_percent,
    verdict,
)


def req(category="skills", desc="x", weight=3, must_have=False, id_=""):
    return Requirement(id=id_, category=category, description=desc, weight=weight, must_have=must_have)


def item(requirement, status):
    return make_scored_item(requirement, Judgement(requirement_id=requirement.id, status=status))


def criteria(reqs, weights=None, min_years=None):
    data = {"role": "Dev", "requirements": [r.model_dump() for r in reqs]}
    if weights:
        data["category_weights"] = weights
    if min_years is not None:
        data["min_total_years"] = min_years
    return HRCriteria.model_validate(data)


# ---------------------------------------------------------------- category_percent
def test_worked_example_from_lld():
    items = [
        item(req(desc="Python", weight=5), "met"),
        item(req(desc="FastAPI or Flask", weight=4), "partial"),
        item(req(desc="SQL databases", weight=3), "not_met"),
    ]
    assert category_percent(items) == pytest.approx(58.33, abs=0.01)


def test_all_met_is_100():
    assert category_percent([item(req(weight=w), "met") for w in (1, 3, 5)]) == 100


def test_all_not_met_is_0():
    assert category_percent([item(req(weight=w), "not_met") for w in (1, 3, 5)]) == 0


def test_empty_items_is_0():
    assert category_percent([]) == 0.0


# ---------------------------------------------------------------- overall_percent
def test_overall_uses_category_weights():
    items = [item(req("skills"), "met"), item(req("experience"), "not_met"), item(req("projects"), "not_met")]
    results = build_category_results(items)
    assert overall_percent(results, {"skills": 50, "experience": 30, "projects": 20}) == 50


def test_overall_renormalises_when_category_empty():
    # No projects requirements: skills 50 and experience 30 become 62.5% / 37.5%.
    items = [item(req("skills"), "met"), item(req("experience"), "not_met")]
    results = build_category_results(items)
    assert overall_percent(results, {"skills": 50, "experience": 30, "projects": 20}) == pytest.approx(62.5)


def test_overall_equal_weights_fallback_when_present_weights_zero():
    items = [item(req("skills"), "met"), item(req("projects"), "not_met")]
    results = build_category_results(items)
    weights = {"skills": 0, "experience": 100, "projects": 0}
    assert overall_percent(results, weights) == 50


# ---------------------------------------------------------------- verdict
@pytest.mark.parametrize(
    "percent, expected",
    [(100, "Strong match"), (75, "Strong match"), (74.9, "Partial match"), (50, "Partial match"), (49.9, "Weak match"), (0, "Weak match")],
)
def test_verdict_bands(percent, expected):
    assert verdict(percent, []) == expected


def test_missing_must_have_overrides_high_score():
    assert verdict(90, ["Python"]) == "Not a match"


# ---------------------------------------------------------------- build_result
def test_build_result_flags_missing_must_have_but_keeps_percent():
    c = criteria([req("skills", "Python", 5, True), req("skills", "SQL", 5)])
    items = [item(c.requirements[0], "not_met"), item(c.requirements[1], "met")]
    result = build_result(c, items, total_years=3.0)
    assert result.verdict == "Not a match"
    assert result.missing_must_haves == ["Python"]
    assert result.overall_percent == 50.0


def test_partial_must_have_is_not_missing():
    c = criteria([req("skills", "Python", 5, True)])
    result = build_result(c, [item(c.requirements[0], "partial")], total_years=1.0)
    assert result.missing_must_haves == []
    assert result.verdict == "Partial match"


def test_min_years_warning_does_not_change_percent():
    c = criteria([req("skills", "Python", 5)], min_years=5)
    result = build_result(c, [item(c.requirements[0], "met")], total_years=2.0)
    assert result.meets_min_years is False
    assert result.overall_percent == 100.0
    assert any("below the required" in w for w in result.warnings)


def test_min_years_none_when_not_set():
    c = criteria([req("skills", "Python", 5)])
    result = build_result(c, [item(c.requirements[0], "met")], total_years=2.0)
    assert result.meets_min_years is None


# ---------------------------------------------------------------- HRCriteria validation
def test_category_weights_must_sum_to_100():
    with pytest.raises(ValidationError, match="sum to 100"):
        criteria([req()], weights={"skills": 50, "experience": 30, "projects": 30})


def test_partial_weights_dict_is_filled_with_zero():
    c = criteria([req()], weights={"skills": 100})
    assert c.category_weights == {"skills": 100, "experience": 0, "projects": 0}


def test_ids_are_assigned_per_category():
    c = criteria([req("skills"), req("skills"), req("projects")])
    assert [r.id for r in c.requirements] == ["skills-1", "skills-2", "projects-1"]


def test_duplicate_ids_rejected():
    with pytest.raises(ValidationError, match="unique"):
        criteria([req(id_="a"), req(id_="a")])


def test_weight_out_of_range_rejected():
    with pytest.raises(ValidationError):
        Requirement(category="skills", description="x", weight=9)


def test_sample_criteria_file_is_valid():
    path = Path(__file__).resolve().parent.parent / "criteria" / "python_backend.json"
    c = HRCriteria.model_validate(json.loads(path.read_text()))
    assert c.role == "Python Backend Developer"
    assert len(c.requirements) == 5
    assert c.requirements[0].id == "skills-1"
