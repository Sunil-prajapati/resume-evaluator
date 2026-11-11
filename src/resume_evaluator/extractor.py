"""Resume text -> structured ResumeData (one LLM call), plus the deterministic experience calculator."""

import re
import sys
from datetime import date

from .errors import ResumeEvaluatorError
from .llm import call_structured
from .models import Job, ResumeData
from .prompts import EXTRACT_SYSTEM, wrap_resume


def extract_resume(text: str, *, debug: bool = False, **llm_kwargs) -> ResumeData:
    return call_structured(EXTRACT_SYSTEM, wrap_resume(text), ResumeData, debug=debug, **llm_kwargs)


# --------------------------------------------------------------------------- experience years
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_PRESENT = {"present", "current", "now", "ongoing", "till date", "to date", "today"}


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def parse_date(value: str | None, *, is_end: bool, today: date) -> int | None:
    """Convert a date string to a month index (year*12 + month-1), or None if unparseable.

    Accepts "YYYY-MM", "YYYY/MM", "YYYY", "Jun 2022", "June 2022" and, for an end date, "present".
    A bare year means January for a start date and December for an end date.
    """
    if not value:
        return None
    s = value.strip().lower()
    if s in _PRESENT:
        return _month_index(today.year, today.month) if is_end else None
    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})", s):
        year, month = int(m[1]), int(m[2])
        return _month_index(year, month) if 1 <= month <= 12 else None
    if m := re.fullmatch(r"(\d{4})", s):
        return _month_index(int(m[1]), 12 if is_end else 1)
    if m := re.fullmatch(r"([a-z]{3,9})\.?,?\s+(\d{4})", s):
        month = _MONTHS.get(m[1][:3])
        return _month_index(int(m[2]), month) if month else None
    return None


def total_years(jobs: list[Job], today: date | None = None) -> tuple[float, list[str]]:
    """Total professional experience in years (1 decimal) and any warnings.

    Each job covers its start month through its end month inclusive. Overlapping jobs are merged so
    parallel employment is not double counted. Jobs with a missing or unreadable date are skipped
    with a warning. End dates in the future are clamped to the current month.
    """
    today = today or date.today()
    now = _month_index(today.year, today.month)
    warnings: list[str] = []
    intervals: list[tuple[int, int]] = []  # half-open [start, end)

    for job in jobs:
        label = f"'{job.title}' at {job.company}"
        start = parse_date(job.start, is_end=False, today=today)
        end = parse_date(job.end, is_end=True, today=today)
        if start is None or end is None:
            warnings.append(f"Experience for {label} skipped: start/end date missing or unreadable ({job.start!r} to {job.end!r}).")
            continue
        end = min(end, now)
        if end < start:
            warnings.append(f"Experience for {label} skipped: end date is before the start date or in the future.")
            continue
        intervals.append((start, end + 1))

    intervals.sort()
    merged: list[list[int]] = []
    for s, e in intervals:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    months = sum(e - s for s, e in merged)
    return round(months / 12, 1), warnings


if __name__ == "__main__":
    # Manual smoke test (makes ONE Groq call):
    #   uv run python -m resume_evaluator.extractor samples/arjun_mehta.docx [--debug]
    from .parser import extract_text

    args = [a for a in sys.argv[1:] if a != "--debug"]
    if len(args) != 1:
        raise SystemExit("usage: python -m resume_evaluator.extractor <resume.pdf|resume.docx> [--debug]")
    try:
        data = extract_resume(extract_text(args[0]), debug="--debug" in sys.argv)
    except (ResumeEvaluatorError, FileNotFoundError, ValueError) as e:
        raise SystemExit(f"Error: {e}")
    print(data.model_dump_json(indent=2))
    years, notes = total_years(data.jobs)
    print(f"\nTotal experience: {years} years")
    for n in notes:
        print(f"warning: {n}")
