"""Command line entry point.

    uv run resume-evaluator --resume samples/arjun_mehta.docx --criteria criteria/python_backend.json
"""

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .errors import ResumeEvaluatorError
from .evaluate import evaluate_file
from .models import HRCriteria
from .report import format_report, save_json


def load_criteria(path: Path) -> HRCriteria:
    if not path.is_file():
        raise FileNotFoundError(f"Criteria file not found: {path}")
    try:
        return HRCriteria.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        raise ResumeEvaluatorError(f"{path} is not valid JSON: {e}") from e
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'criteria'}: {err['msg']}" for err in e.errors())
        raise ResumeEvaluatorError(f"Invalid criteria file {path}: {problems}") from e


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="resume-evaluator",
        description="Score a resume (.pdf / .docx) against an HR criteria file using an LLM.",
    )
    p.add_argument("--resume", required=True, type=Path, help="path to the resume (.pdf or .docx)")
    p.add_argument("--criteria", required=True, type=Path, help="path to the HR criteria JSON file")
    p.add_argument("--out", type=Path, default=Path("output"), help="folder for the JSON report (default: output/)")
    p.add_argument("--debug", action="store_true", help="print the raw LLM output for every call")
    return p


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy codepage; quotes/ellipses from the resume would crash print().
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    try:
        criteria = load_criteria(args.criteria)
        result = evaluate_file(args.resume, criteria, debug=args.debug)
    except (ResumeEvaluatorError, FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(format_report(result))
    report_path = save_json(result, args.out, args.resume.stem)
    print(f"\nFull report saved to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
