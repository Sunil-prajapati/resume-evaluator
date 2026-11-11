# Resume Evaluator

Scores a resume (PDF or Word) against an HR criteria list using an LLM (Groq, `openai/gpt-oss-120b`) and
reports a match percentage with evidence for every decision. Design: [HLD.md](HLD.md), [LLD.md](LLD.md),
build plan: [PHASES.md](PHASES.md).

## Setup (once)

Needs [uv](https://docs.astral.sh/uv/) and a `GROQ_API_KEY` in `d:\Project\LLM\.env` (found automatically).

```powershell
cd D:\Project\LLM\practical\resume_evaluator
uv sync
```

## Run

```powershell
uv run resume-evaluator --resume samples\arjun_mehta.docx --criteria criteria\python_backend.json
```

| Option | Meaning |
|---|---|
| `--resume PATH` | resume file, `.pdf` or `.docx` (required) |
| `--criteria PATH` | HR criteria JSON (required) |
| `--out DIR` | where the JSON report goes (default `output\`) |
| `--debug` | print the raw LLM output of every call |

Each run makes 1 + (number of non-empty categories) Groq calls, usually 4, and takes about 30 seconds.
It prints a report and saves `output\<resume name>_report.json`. Exit code 0 on success, 1 on any error.

Step-by-step helpers:

```powershell
uv run python -m resume_evaluator.parser samples\arjun_mehta.docx      # just the extracted text (no LLM)
uv run python -m resume_evaluator.extractor samples\arjun_mehta.docx   # extracted data + years (1 Groq call)
```

## HR criteria file

```json
{
  "role": "Python Backend Developer",
  "min_total_years": 2,
  "category_weights": {"skills": 50, "experience": 30, "projects": 20},
  "requirements": [
    {"category": "skills", "description": "Python", "must_have": true, "weight": 5},
    {"category": "projects", "description": "Built and deployed a REST API", "weight": 4}
  ]
}
```

- `category`: `skills`, `experience` or `projects`.
- `weight`: 1 to 5 (default 3). `must_have`: a requirement judged `not_met` forces the verdict "Not a match".
- `category_weights` must sum to 100 and can be omitted (default 50 / 30 / 20). Unused categories are ignored.
- `min_total_years` is optional; it adds a warning but does not change the percentage.

## Tests

```powershell
uv run pytest                      # 115 offline tests, a few seconds, no API key needed
uv run pytest -m integration -v    # 6 real-API tests, ~2.5 minutes, ~20 Groq calls
```

## Known limitations

- Scanned (image-only) PDFs and old `.doc` files are not supported.
- `total_years_experience` counts all jobs, relevant or not. Use an `experience` requirement for relevance.
- The verifier proves a quote exists in the resume, not that it supports the claim. Judgement quality still
  depends on the model.
- The whole resume text, including name and contact details, is sent to Groq. Do not use real resumes unless
  that is acceptable. `samples\` and `output\` are git-ignored.
