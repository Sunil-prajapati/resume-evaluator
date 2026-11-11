import pytest
from fakes import RESUME_TEXT, j

from resume_evaluator.models import Judgement
from resume_evaluator.verifier import evidence_in_text, verify


# ---------------------------------------------------------------- evidence_in_text
def test_exact_quote_found():
    assert evidence_in_text("Maintain Flask REST APIs handling 50k daily orders in production", RESUME_TEXT)


def test_case_whitespace_and_punctuation_ignored():
    assert evidence_in_text("maintain  FLASK rest apis,\nhandling 50K daily orders", RESUME_TEXT)


def test_ellipsis_fragments_each_checked():
    assert evidence_in_text("Built a REST API with Flask ... deployed on AWS EC2", RESUME_TEXT)


def test_one_bad_fragment_fails_the_whole_quote():
    assert not evidence_in_text("Built a REST API with Flask ... led a team of 12 engineers", RESUME_TEXT)


def test_invented_quote_rejected():
    assert not evidence_in_text("Led a team of 10 engineers at Google", RESUME_TEXT)


def test_scattered_real_words_rejected():
    # Every word exists somewhere in the resume, but never together in this order.
    assert not evidence_in_text("Built Python Flask API production systems Docker Django orders", RESUME_TEXT)


def test_empty_or_punctuation_only_evidence_rejected():
    assert not evidence_in_text("", RESUME_TEXT)
    assert not evidence_in_text("...", RESUME_TEXT)


def test_pdf_hyphenation_artefact_tolerated():
    text = "Designed micro-\nservices architecture for the billing platform."
    assert evidence_in_text("Designed microservices architecture", text)


def test_long_quote_with_one_wrong_word_tolerated():
    quote = "Moved report generation to PostgreSQL materialized views reducing load time by 60"
    assert evidence_in_text(quote, RESUME_TEXT)  # resume says "cutting", not "reducing"


def test_short_quote_with_one_wrong_word_not_tolerated():
    assert not evidence_in_text("Maintain Django REST APIs", RESUME_TEXT)


# ---------------------------------------------------------------- verify
def judgement(status, evidence="", reasoning="because"):
    return Judgement.model_validate(j("skills-1", status, evidence, reasoning))


def test_not_met_needs_no_evidence():
    out, verified, downgraded = verify(judgement("not_met"), RESUME_TEXT)
    assert (verified, downgraded, out.status) == (True, False, "not_met")


def test_met_with_real_evidence_kept():
    ev = "Maintain Flask REST APIs handling 50k daily orders"
    out, verified, downgraded = verify(judgement("met", ev), RESUME_TEXT)
    assert (verified, downgraded, out.status) == (True, False, "met")


def test_partial_with_real_evidence_kept():
    out, verified, downgraded = verify(judgement("partial", "Skills: Python, SQL, Flask"), RESUME_TEXT)
    assert (verified, downgraded, out.status) == (True, False, "partial")


@pytest.mark.parametrize("status", ["met", "partial"])
def test_fabricated_evidence_downgraded(status):
    out, verified, downgraded = verify(judgement(status, "Led migration of 40 services to Kubernetes"), RESUME_TEXT)
    assert (verified, downgraded, out.status) == (False, True, "not_met")
    assert "not found" in out.reasoning and status in out.reasoning


def test_met_without_evidence_downgraded():
    out, verified, downgraded = verify(judgement("met", ""), RESUME_TEXT)
    assert (verified, downgraded, out.status) == (False, True, "not_met")
    assert "no evidence" in out.reasoning


def test_verify_does_not_mutate_input():
    original = judgement("met", "made up quote that is not in the resume at all")
    verify(original, RESUME_TEXT)
    assert original.status == "met"
