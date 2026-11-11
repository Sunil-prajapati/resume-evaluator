"""Human-readable console report and machine-readable JSON report."""

from pathlib import Path

from .models import EvaluationResult

_LABEL = {"met": "met", "partial": "partial", "not_met": "not_met"}


def _clip(text: str, width: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def format_report(result: EvaluationResult) -> str:
    lines = [
        f"Role: {result.role}",
        f"Overall match: {result.overall_percent:.1f}%    Verdict: {result.verdict}",
        f"Total experience: {result.total_years_experience:.1f} years"
        + ("" if result.meets_min_years is None else f" (minimum met: {'yes' if result.meets_min_years else 'NO'})"),
        "",
    ]
    for cat in result.category_results:
        lines.append(f"{cat.category.upper()} ({cat.percent:.1f}%)")
        for item in cat.items:
            tag = f"[{_LABEL[item.status]}]".ljust(10)
            must = " *must-have*" if item.requirement.must_have else ""
            lines.append(f"  {tag} {item.requirement.description}{must}")
            if item.evidence:
                mark = "" if item.evidence_verified else " (unverified)"
                lines.append(f'             "{_clip(item.evidence)}"{mark}')
            elif item.status != "not_met" or item.downgraded:
                lines.append("             (no evidence)")
            if item.downgraded:
                lines.append("             ! downgraded: quote not found in resume")
        lines.append("")

    lines.append("Missing must-haves: " + (", ".join(result.missing_must_haves) or "none"))
    if result.warnings:
        lines.append("Warnings:")
        lines += [f"  - {w}" for w in result.warnings]
    return "\n".join(lines)


def save_json(result: EvaluationResult, out_dir: str | Path, stem: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}_report.json"
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    return path
