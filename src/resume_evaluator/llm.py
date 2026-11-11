"""The single gateway to the LLM.

Same pattern as day4/json_pydantic.py (schema in the prompt, JSON mode, Pydantic validation),
plus two kinds of retry:
  * invalid output  -> send the validation error back to the model and ask it to fix its JSON
  * transient errors (rate limit, network, 5xx) -> exponential backoff
"""

import json
import time
from typing import TypeVar

import groq
from groq import Groq
from pydantic import BaseModel, ValidationError

from . import config
from .errors import LLMOutputError, ResumeEvaluatorError

T = TypeVar("T", bound=BaseModel)

BACKOFF_SECONDS = (1, 2, 4)
_client: Groq | None = None


def get_client() -> Groq:
    """Create the Groq client on first use (so importing this module needs no API key)."""
    global _client
    if _client is None:
        _client = Groq(api_key=config.get_api_key())
    return _client


def call_structured(
    system: str,
    user: str,
    model_cls: type[T],
    *,
    client: Groq | None = None,
    sleep=time.sleep,
    debug: bool = False,
) -> T:
    """Ask the LLM for JSON matching `model_cls` and return the validated object.

    Raises LLMOutputError if no valid output after 1 + MAX_RETRIES attempts, or if the API
    stays unavailable after the backoff attempts.
    """
    client = client or get_client()
    schema = json.dumps(model_cls.model_json_schema(), indent=2)
    messages = [
        {
            "role": "system",
            "content": f"{system}\n\nReturn ONLY a JSON object that strictly follows this JSON schema. "
            f"Do not add fields that are not in the schema.\n{schema}",
        },
        {"role": "user", "content": user},
    ]

    last_error: Exception | None = None
    for attempt in range(config.MAX_RETRIES + 1):
        raw = _complete(client, messages, sleep)
        if debug:
            print(f"[llm attempt {attempt + 1}] raw output:\n{raw}\n")
        try:
            if raw is None:
                raise ValueError("model returned an empty response")
            return model_cls.model_validate_json(raw)
        except (ValidationError, ValueError) as e:
            last_error = e
            # Feed the error back so the model can repair its own output.
            messages += [
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content": f"That JSON failed validation:\n{e}\nReturn corrected JSON only."},
            ]
    raise LLMOutputError(
        f"Model did not return valid output after {config.MAX_RETRIES + 1} attempts. Last error: {last_error}"
    )


def _complete(client: Groq, messages: list[dict], sleep) -> str | None:
    """One chat completion, retrying transient API failures with backoff."""
    for delay in (*BACKOFF_SECONDS, None):
        try:
            resp = client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=config.TEMPERATURE,
            )
            return resp.choices[0].message.content
        except groq.BadRequestError as e:
            # JSON mode rejects output that is not valid JSON; treat it as an invalid attempt, not a crash.
            if "json_validate_failed" in str(e):
                return None
            raise ResumeEvaluatorError(f"Groq rejected the request: {e}") from e
        except groq.AuthenticationError as e:
            raise ResumeEvaluatorError("Groq authentication failed. Check GROQ_API_KEY in your .env file.") from e
        except (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError) as e:
            if delay is None:
                raise LLMOutputError(f"Groq unavailable after {len(BACKOFF_SECONDS) + 1} tries ({type(e).__name__}). Try again later.") from e
            sleep(delay)
    raise AssertionError("unreachable")
