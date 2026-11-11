"""Settings and constants. Importing this module has no side effects, so tests need no API key."""

import os
from pathlib import Path

from dotenv import load_dotenv

MODEL = "openai/gpt-oss-120b"
TEMPERATURE = 0
MAX_RETRIES = 2  # extra attempts after the first one
MIN_RESUME_CHARS = 200

DEFAULT_CATEGORY_WEIGHTS = {"skills": 50, "experience": 30, "projects": 20}

STRONG_THRESHOLD = 75
PARTIAL_THRESHOLD = 50

STATUS_SCORE = {"met": 1.0, "partial": 0.5, "not_met": 0.0}


def _find_env() -> Path | None:
    """Walk up from this file until a .env is found (d:\\Project\\LLM\\.env in this repo)."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


def get_api_key() -> str:
    """Load GROQ_API_KEY from .env / environment. Called lazily by the LLM layer."""
    env_path = _find_env()
    if env_path:
        load_dotenv(env_path)
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise ValueError("GROQ_API_KEY not found. Set it in your .env file.")
    return key
