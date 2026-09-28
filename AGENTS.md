# AGENTS.md

Instructions for AI coding agents working on this repository.

## What this project is

The **Question Metadata Engine (QME)** — a backend AI pipeline that transforms raw aptitude questions into structured, validated, metadata-rich objects (classification, difficulty, solutions, formulas). It is NOT a chatbot, test generator, student app, or deduplication system.

## Read before writing any code

1. `docs/AI_IMPLEMENTATION_GUIDE.md` — project overview, constraints, quality requirements, pitfalls (§11 Getting Started, §14 Files to Create First)
2. `docs/IMPLEMENTATION_ORDER.md` — the ordered build sequence (Steps 1–12). **Build only the current step.**
3. `docs/PROJECT_STRUCTURE.md` — exact folder/file layout
4. `docs/API_CONTRACTS.md` — Pydantic models and Protocol interfaces (single source of truth)
5. Feature specs in `docs/FEATURES/FE-*.md` — acceptance criteria per feature
6. `docs/SERVICES/metadata-engine/TESTING.md` — test organization and strategy

## Hard rules

- **One step per session.** Never start the next implementation step, even if it seems trivial.
- **No code outside `src/qme/` and `tests/`.** Docs live in `docs/`.
- **Models are the contract.** `core/models.py` must match `docs/API_CONTRACTS.md` §3 exactly. Do not invent fields.
- **Structured LLM outputs only.** Never parse free-form LLM text; always enforce a Pydantic schema via `response_format`.
- **No silent failures.** Every error is logged with context; status is always set explicitly.
- **Every stage implements its Protocol** from `core/protocols.py`. Modules must stay swappable.
- **Provenance everywhere.** Every output question carries source + model + prompt version + timestamp.
- **Run gates before reporting done:** `make test` and `make lint` must pass.

## Current milestone

Check `docs/ROADMAP.md` and `docs/IMPLEMENTATION_ORDER.md` to determine the current step. Update this section when a milestone closes.

- **Current:** M3 — Taxonomy & Classification (Step 3): seed taxonomy, `taxonomy_loader`, LLM gateway + structured output + prompt manager, `QuestionClassifier` stage
- **Closed:** M1 — Project Skeleton (Step 1); M2 — Ingestion (Step 2): JSONL/CSV/TXT parsers, normalizer, source tracker, `qme ingest` (134 tests). Docker files deferred (no Docker on this machine) until the deployment milestone.
- **Next exit gate (M3):** `QuestionClassifier.classify()` returns a `ClassificationResult` through enforced structured output; unit tests pass with a mocked gateway; opt-in `ai_eval` gold-standard classification eval runs against `tests/ai_evaluation/gold_standard/`.

## Verification commands

```bash
pytest tests -q   # all tests (134 as of M2 close)
ruff check src tests
mypy
make test         # same, via Makefile (requires GNU make; use commands above on Windows)
make run-api      # uvicorn dev server
qme --help        # CLI smoke test
curl http://localhost:8000/api/v1/health
```
