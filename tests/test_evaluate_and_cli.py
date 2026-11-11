import json
from datetime import date
from pathlib import Path

import docx
import pytest
from fakes import RESUME_JSON, RESUME_TEXT, FakeClient, batch, j

from resume_evaluator import llm
from resume_evaluator.cli import main
from resume_evaluator.evaluate import evaluate_text
from resume_evaluator.models import HRCriteria
from resume_evaluator.report import format_report

CRITERIA_PATH = Path(__file__).resolve().parent.parent / "criteria" / "python_backend.json"
TODAY = date(2026, 11, 11)


def criteria() -> HRCriteria:
    return HRCriteria.model_validate(json.loads(CRITERIA_PATH.read_text()))


def scripted_client(*, fabricate_flask=True):
    """extraction, then skills / experience / projects batches (the order evaluate_text calls them)."""
    flask_evidence = "Led migration of 40 services to Kubernetes" if fabricate_flask else "Maintain Flask REST APIs"
    return FakeClient(
        [
            RESUME_JSON,
            batch(
                j("skills-1", "met", "Skills: Python, SQL, Flask"),
                j("skills-2", "met", flask_evidence),
                j("skills-3", "not_met"),
            ),
            batch(j("experience-1", "met", "Maintain Flask REST APIs handling 50k daily orders in production")),
            batch(j("projects-1", "partial", "Built a REST API with Flask and PostgreSQL")),
        ]
    )


# ---------------------------------------------------------------- pipeline
def test_pipeline_end_to_end_with_downgrade():
    client = scripted_client()
    result = evaluate_text(RESUME_TEXT, criteria(), today=TODAY, client=client)

    assert len(client.calls) == 4  # 1 extraction + 3 categories
    skills = result.category_results[0]
    assert [i.status for i in skills.items] == ["met", "not_met", "not_met"]  # skills-2 downgraded
    assert skills.items[1].downgraded and not skills.items[1].evidence_verified
    assert skills.percent == pytest.approx(100 * 5 / 12)
    assert result.overall_percent == 60.8
    assert result.verdict == "Partial match"
    assert result.total_years_experience == 4.5  # Jun 2022..Nov 2026, computed by code
    assert result.meets_min_years is True
    assert any("FastAPI or Flask" in w and "Downgraded" in w for w in result.warnings)


def test_pipeline_without_fabrication_has_no_downgrade_warning():
    result = evaluate_text(RESUME_TEXT, criteria(), today=TODAY, client=scripted_client(fabricate_flask=False))
    assert not any("Downgraded" in w for w in result.warnings)
    assert result.category_results[0].items[1].status == "met"


def test_report_text_contains_the_key_facts():
    result = evaluate_text(RESUME_TEXT, criteria(), today=TODAY, client=scripted_client())
    text = format_report(result)
    assert "Overall match: 60.8%" in text and "Partial match" in text
    assert "SKILLS (41.7%)" in text
    assert "[not_met]" in text and "downgraded" in text
    assert "Missing must-haves: none" in text


# ---------------------------------------------------------------- CLI
@pytest.fixture
def resume_file(tmp_path):
    d = docx.Document()
    for line in RESUME_TEXT.splitlines():
        d.add_paragraph(line)
    path = tmp_path / "candidate.docx"
    d.save(path)
    return path


def test_cli_happy_path_prints_report_and_writes_json(monkeypatch, capsys, resume_file, tmp_path):
    monkeypatch.setattr(llm, "_client", scripted_client(fabricate_flask=False))
    out_dir = tmp_path / "out"
    code = main(["--resume", str(resume_file), "--criteria", str(CRITERIA_PATH), "--out", str(out_dir)])

    assert code == 0
    printed = capsys.readouterr().out
    assert "Role: Python Backend Developer" in printed and "Overall match:" in printed
    report = json.loads((out_dir / "candidate_report.json").read_text(encoding="utf-8"))
    assert report["role"] == "Python Backend Developer"
    assert report["verdict"] in {"Strong match", "Partial match", "Weak match", "Not a match"}


def test_cli_missing_criteria_file(capsys, resume_file, tmp_path):
    assert main(["--resume", str(resume_file), "--criteria", str(tmp_path / "nope.json")]) == 1
    assert "Criteria file not found" in capsys.readouterr().err


def test_cli_invalid_criteria_names_the_problem(capsys, resume_file, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"role": "X", "category_weights": {"skills": 90}, "requirements": [{"category": "skills", "description": "a"}]}))
    assert main(["--resume", str(resume_file), "--criteria", str(bad)]) == 1
    assert "sum to 100" in capsys.readouterr().err


def test_cli_criteria_not_json(capsys, resume_file, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert main(["--resume", str(resume_file), "--criteria", str(bad)]) == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_cli_unsupported_resume_format(capsys, tmp_path):
    txt = tmp_path / "resume.txt"
    txt.write_text("x" * 500)
    assert main(["--resume", str(txt), "--criteria", str(CRITERIA_PATH)]) == 1
    assert "Only .pdf and .docx" in capsys.readouterr().err


def test_cli_missing_resume(capsys, tmp_path):
    assert main(["--resume", str(tmp_path / "nope.pdf"), "--criteria", str(CRITERIA_PATH)]) == 1
    assert "Resume not found" in capsys.readouterr().err
