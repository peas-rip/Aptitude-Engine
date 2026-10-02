# Aptitude-Engine

**Question Metadata Engine (QME)** — a backend AI pipeline that transforms raw aptitude
questions into structured, validated, metadata-rich objects (classification, difficulty,
solutions, formulas). Not a chatbot, test generator, or student app: QME produces the
structured data that downstream agents consume.

## Status (2026-10-02)

### Completed — 4 of 12 roadmap steps

| Milestone | Step | Delivered | Live gate |
|---|---|---|---|
| M1 Skeleton | 1 | Contracts (`core/models.py`, `protocols.py`), settings, FastAPI `/api/v1/health`, Typer CLI | health smoke |
| M2 Ingestion | 2 | JSONL/CSV/TXT parsers, normalizer, source tracker, `qme ingest` | 134 tests |
| M3 Classification | 3 | Seed taxonomy (4 categories / 34 topics / 70 subtopics), LLM gateway (Gemini free tier, strict structured output), `Classifier` stage | category **25/25**, topic **25/25**, subtopic **22/24** |
| M4 Difficulty | 4 | `difficulty_v1` tier-first prompt, pure scoring functions, reasoning-led factor weights, `DifficultyEngine` stage, 25-question gold standard | Pearson correlation **0.883 ≥ 0.8** |
| Test & Practice Agent | — | `src/qme/testgen/` — blueprint-conformant test & practice assembly from the external agent's bank, `qme testgen` / `qme practice` (no LLM) | 60 tests, live bank smoke |

Quality gates on `main`: **301 offline tests passing**, `ruff check src tests` clean,
`mypy` clean (45 files). Three opt-in live evals deselected by default (`pytest -m ai_eval`).

### Current work

- **Question enrichment is delivered externally.** An existing agent produced the
  active deliverables in `data/input/` (the three contract files below are
  tracked so git-based deploys ship them; raw book sources stay ignored):
  - `book_questions_agent_ready.jsonl` — 1,310 questions with chapter/topic/difficulty labels, agent metadata, answer-key-anchored solutions
  - `aptitude_agent_knowledge.json` — 17-chapter knowledge bank (formulas, short tricks, web sources)
  - `aptitude_test_blueprint.json` — test-generation contract (filters, selection rules, bucket counts, output fields)
- **QME's pipeline is parked at M4** (owner decision). Resume point if unparked:
  M5 Solution Engine — genuine step-by-step solutions with answer-key validation,
  the gap left by the external agent's template solutions (`solution_basis: source_answer_key_plus_topic_method`).
- **Delivered:** the Test & Practice Agent (`qme testgen` / `qme practice`) — a
  deterministic assembler that consumes the three files above and produces
  blueprint-shaped tests and difficulty-graded practice sets. Contract mismatches
  hard-stop with a field-level report. No LLM calls, no rate limits. See
  `docs/AGENT_SUMMARY.md`.

### Parked / deferred (owner decision)

General PDF/DOCX parsers (book already converted), PostgreSQL, evaluation harness,
API polish, Docker (no Docker on this machine). The interim corpus batch runner
lives at `tests/batch/` and is superseded by the external agent's output.

## Repository layout

```
src/qme/
  core/         # models (API_CONTRACTS), protocols, constants, exceptions
  config/       # settings, taxonomy loader, LLM prompt templates
  ingestion/    # parsers (jsonl/csv/txt), normalizer, source tracker
  llm/          # gateway (Gemini/OpenAI-compatible), prompt manager
  pipeline/     # stages: classifier, difficulty
  testgen/      # test & practice agent
  utils/        # difficulty scoring math
  api/  cli.py  # FastAPI app, Typer CLI
tests/          # unit, integration, failure, regression, batch, ai_evaluation
docs/           # architecture, contracts, feature specs, AGENT_SUMMARY.md
data/           # upstream bank (3 contract files tracked; raw sources & outputs ignored)
```

## Running

```bash
pip install -e ".[dev]"

pytest tests -q            # offline gates (ai_eval deselected)
ruff check src tests
mypy

qme --help                 # CLI
qme ingest --input data/samples/sample_questions.jsonl --output data/output/run1
uvicorn qme.main:app --port 8000   # or: make run-api

# live evals (needs GEMINI_API_KEY in .env)
pytest -m ai_eval
```

Provider: Gemini free tier by default (`.env` carries the key; `.env.example` lists
all model overrides). See `AGENTS.md` for agent-facing rules and milestone state.

## Deployment

The Test & Practice API (`API_CONTRACTS` §1.7) targets **Railway** (any
git-based PaaS works): push to `main` → Nixpacks builds `pyproject.toml` →
service boots. The three bank files in `data/input/` ship with the repo.

**Service configuration (Railway dashboard):**

| Setting | Value |
|---|---|
| Start command | `uvicorn qme.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/v1/health` (open, keyless) |
| `ENVIRONMENT` | `production` (app refuses to boot without a key) |
| `QME_API_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `QME_BLUEPRINT_PATH` | optional — defaults to `data/input/aptitude_test_blueprint.json` |

**Consumer runbook:**

```bash
BASE=https://<app>.up.railway.app
curl $BASE/api/v1/health                                  # 200, no key
curl -H "X-API-Key: $QME_API_KEY" $BASE/api/v1/bank/meta  # discovery
curl -X POST -H "X-API-Key: $QME_API_KEY" -H 'Content-Type: application/json' \
  -d '{"seed":42,"selections":[{"count":20,"difficulty":"hard"}]}' \
  $BASE/api/v1/tests                                      # 200 GeneratedTest
```

Errors follow `API_CONTRACTS` §4: 401 `UNAUTHORIZED` (missing/wrong key),
422 `VALIDATION_ERROR`/`INVALID_INPUT` (`details` lists available filters),
503 `SERVICE_UNAVAILABLE` (bank contract report in `details.issues`). The
bank reloads automatically when its files change (mtime check) — update the
bank by committing the changed files and pushing.
