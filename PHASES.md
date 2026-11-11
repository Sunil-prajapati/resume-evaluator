# Resume Evaluator: Build Phases

Each phase ends with something you can run or test, so you always know it works before moving on.
Design details live in [HLD.md](HLD.md) and [LLD.md](LLD.md).

| Phase | Name | Needs LLM? | Done when |
|---|---|---|---|
| 1 | Foundation: project, config, models, scoring | No | `pytest` passes; the worked example (58.3%) is reproduced |
| 2 | Document parser (PDF / DOCX to text) | No | A sample PDF and DOCX print clean text; bad files give clear errors |
| 3 | LLM gateway + resume extractor | Yes (1 call) | A resume prints as a valid `ResumeData` object |
| 4 | Experience years calculator | No | Overlap, "present" and year-only dates are tested |
| 5 | Matcher + evidence verifier | Yes (3 calls) | Each HR requirement gets a verified judgement |
| 6 | Report + CLI (end-to-end) | Yes | `resume-evaluator --resume X --criteria Y` prints the % and writes JSON |
| 7 | Hardening and integration tests | Yes | Determinism and prompt-injection checks pass |

## Phase 1: Foundation (DONE: 24 tests passing)
- `uv` package scaffold, dependencies, `.gitignore`
- `config.py` (env, model, thresholds)
- `models.py` (HR criteria, resume data, judgements, results)
- `scoring.py` (pure functions) and `tests/test_scoring.py`
- Example criteria file `criteria/python_backend.json`

## Phase 2: Document parser (DONE: 37 tests passing)
- `parser.py` for PDF (`pypdf`) and DOCX (`python-docx`, including tables)
- Text normalisation and the scanned-PDF guard
- `tests/test_parser.py`

## Phase 3: LLM gateway + extractor (DONE: 51 tests passing, real Groq call verified)
- `llm.py` with JSON mode, Pydantic validation, retry with error feedback, backoff
- `prompts.py` (extraction prompt)
- `extractor.py`, with a manual smoke script

## Phase 4: Experience years (DONE)
- `total_years()` with interval merging
- `tests/test_experience_years.py`

## Phase 5: Matcher + verifier (DONE)
- Matching prompt, `matcher.py` (one call per category, `reconcile`)
- `verifier.py` (substring check with fuzzy fallback)
- `tests/test_verifier.py`

## Phase 6: Report + CLI (DONE)
- `report.py` (console and JSON), `cli.py` (`argparse`, `--debug`), script entry point

## Phase 7: Hardening (DONE: 115 offline + 6 integration tests passing)
- Sample resumes (strong, partial, weak), band assertions, run-twice determinism check
- Prompt-injection resume test
- README with usage
