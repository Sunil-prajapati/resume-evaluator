"""Evidence verifier: an LLM judgement is only trusted if its quote really appears in the resume.

This is the main hallucination guard. A "met"/"partial" claim whose quote cannot be found in the
resume text is downgraded to "not_met".
"""

import re
from difflib import SequenceMatcher

from .models import Judgement

FUZZY_MIN_TOKENS = 8  # shorter quotes must match exactly
FUZZY_RATIO = 0.9  # tolerance for PDF line-break / hyphenation artefacts
COMPACT_MIN_CHARS = 12  # whitespace-insensitive match only for quotes at least this long

_TOKEN = re.compile(r"[a-z0-9]+")
_ELLIPSIS = re.compile(r"\.{3,}|…")


def _tokens(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def evidence_in_text(evidence: str, resume_text: str) -> bool:
    """True if every fragment of `evidence` (split on "...") is found in the resume text.

    Case, punctuation and whitespace differences are ignored.
    """
    text_tokens = _tokens(resume_text)
    text_joined = " " + " ".join(text_tokens) + " "
    text_compact = "".join(text_tokens)

    fragments = [_tokens(f) for f in _ELLIPSIS.split(evidence)]
    fragments = [f for f in fragments if f]
    if not fragments:
        return False
    return all(_fragment_found(f, text_tokens, text_joined, text_compact) for f in fragments)


def _fragment_found(frag: list[str], text_tokens: list[str], text_joined: str, text_compact: str) -> bool:
    if " " + " ".join(frag) + " " in text_joined:
        return True
    compact = "".join(frag)
    if len(compact) >= COMPACT_MIN_CHARS and compact in text_compact:
        return True  # e.g. "micro-\nservices" extracted as "micro services"
    n = len(frag)
    if n < FUZZY_MIN_TOKENS:
        return False
    # Fuzzy: a window of the same length must be almost identical. Scattered words from all over the
    # resume do not count, so an invented quote built from real words still fails.
    for i in range(len(text_tokens) - n + 1):
        if SequenceMatcher(None, frag, text_tokens[i : i + n], autojunk=False).ratio() >= FUZZY_RATIO:
            return True
    return False


def verify(judgement: Judgement, resume_text: str) -> tuple[Judgement, bool, bool]:
    """Check one judgement. Returns (judgement, evidence_verified, downgraded)."""
    if judgement.status == "not_met":
        return judgement, True, False  # nothing to prove

    if judgement.evidence.strip() and evidence_in_text(judgement.evidence, resume_text):
        return judgement, True, False

    reason = "no evidence quoted" if not judgement.evidence.strip() else "quoted evidence not found in the resume"
    downgraded = judgement.model_copy(
        update={
            "status": "not_met",
            "reasoning": f"Downgraded ({reason}). Model said {judgement.status}: {judgement.reasoning}".strip(),
        }
    )
    return downgraded, False, True
