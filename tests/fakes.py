"""Test doubles shared by several test files."""

import json
from types import SimpleNamespace

import httpx

REQ = httpx.Request("POST", "https://api.groq.com/x")


def http_response(status: int) -> httpx.Response:
    return httpx.Response(status, request=REQ)


RESUME_TEXT = """\
Backend developer with 3+ years of experience building Python web services.
Skills: Python, SQL, Flask, Django, Pandas, Docker, Git, PostgreSQL, AWS EC2
Software Engineer, BrightCart Pvt Ltd (Jun 2022 - Present)
Maintain Flask REST APIs handling 50k daily orders in production. Moved report generation to PostgreSQL materialized views, cutting load time by 60%.
Projects
Expense Tracker API - Built a REST API with Flask and PostgreSQL, containerised with Docker and deployed on AWS EC2.
"""

RESUME_JSON = json.dumps(
    {
        "skills": ["Python", "SQL", "Flask", "Django", "Pandas", "Docker", "Git", "PostgreSQL", "AWS EC2"],
        "jobs": [{"title": "Software Engineer", "company": "BrightCart Pvt Ltd", "start": "2022-06", "end": "present"}],
        "projects": [{"name": "Expense Tracker API", "description": "REST API", "technologies": ["Flask"]}],
    }
)


def batch(*judgements: dict) -> str:
    """JSON for a JudgementBatch. Each dict needs requirement_id and status."""
    return json.dumps({"judgements": list(judgements)})


def j(req_id: str, status: str, evidence: str = "", reasoning: str = "ok", confidence: float = 0.9) -> dict:
    return {
        "requirement_id": req_id,
        "status": status,
        "evidence": evidence,
        "reasoning": reasoning,
        "confidence": confidence,
    }


class FakeClient:
    """Stands in for Groq. `script` items are returned as content, or raised if an Exception."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])
