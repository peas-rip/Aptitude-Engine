# AI Implementation Guide: Question Metadata Engine

## 1. Project Overview

**Goal:** Build a backend AI pipeline that transforms raw aptitude questions into structured, validated, metadata-rich objects.

**Input:** Raw questions from JSONL, CSV, TXT, PDF, DOCX, or manual entry.

**Output:** JSONL file (V1) or PostgreSQL (V2+) containing `EnrichedQuestion` objects with:
- Hierarchical classification (category → topic → subtopic)
- Quantitative difficulty (0-10 score, rating, factors, estimated time)
- Step-by-step solutions (extracted or generated)
- Formula references for future KB linking
- Full provenance and validation status

**Downstream Consumer:** Question Deduplication/Ingestion Engine (separate system).

## 2. Architecture Summary

- **Single service** (V1): FastAPI + batch worker in one Docker image
- **Modular pipeline:** Extractor → Classifier → Difficulty → Solution → Formula → Validator → Output
- **Pluggable AI modules:** Each stage implements a Protocol interface for replaceability
- **Structured LLM outputs:** Pydantic models enforced via `response_format`
- **File-based checkpointing:** Resumable batches, no Redis needed
- **JSONL output:** Streamable, line-delimited, deduplication-ready

## 3. Service List

| Service | Status | Description |
|---------|--------|-------------|
| metadata-engine | V1 | Main pipeline service (API + batch worker) |
| classification-service | Future | Split when independent scaling needed |
| solution-service | Future | Split for GPU isolation |
| formula-service | Future | Split when Formula KB exists |
| batch-orchestrator | Future | Multi-tenant, priority queues |

## 4. Feature List

| ID | Feature | Module | Priority |
|----|---------|--------|----------|
| FE-001 | Question Extraction & Normalization | ingestion/ | V1 Core |
| FE-002 | Topic/Subtopic Classification | pipeline/stages/classifier.py | V1 Core |
| FE-003 | Difficulty Scoring | pipeline/stages/difficulty.py | V1 Core |
| FE-004 | Solution Engine | pipeline/stages/solution.py | V1 Core |
| FE-005 | Formula Identification | pipeline/stages/formula.py | V1 Core |
| FE-006 | Multi-Layer Validation | validation/ | V1 Core |
| FE-007 | Batch Processing | pipeline/coordinator.py | V1 Core |
| FE-008 | Source Tracking | ingestion/source_tracker.py | V1 Core |
| FE-009 | Human Review | output/review_queue.py | V1 Core |
| FE-010 | Observability | llm/cost_tracker.py, metrics | V1 Core |

## 5. Development Order (IMPLEMENTATION_ORDER.md)

1. Project Skeleton (models, config, API/CLI skeleton)
2. Ingestion Core (JSONL, CSV, TXT parsers, normalizer)
3. Taxonomy & Classification (seed taxonomy, LLM classifier)
4. Difficulty Engine (multi-factor scoring)
5. Solution Engine (extract + generate)
6. Formula Extraction (formula refs)
7. Validation Pipeline (7 layers)
8. Pipeline Orchestration (batch coordinator, checkpointing, API)
9. Document Parsers (PDF, DOCX)
10. PostgreSQL Integration (schema, import, pgvector)
11. Evaluation Harness (gold standard, regression tests)
12. Polish & Documentation

## 6. Key Constraints

### 6.1 Technical Constraints
- **Language:** Python 3.11+
- **Framework:** FastAPI (async), Pydantic v2
- **LLM:** Provider-pluggable gateway; default **Google Gemini free tier**
  (`gemini-3.5-flash-lite`, strict structured output), Groq free alternative,
  optional OpenAI paid fallback (`QME_LLM_PROVIDER=gemini|groq|openai|custom`)
- **Output:** JSONL (V1), PostgreSQL + pgvector (V2+)
- **Deployment:** Docker Compose on VPS
- **No:** Redis, Queue, Kubernetes, Admin UI (V1)

### 6.2 AI Constraints
- **Structured outputs mandatory:** Never parse free-form LLM text
- **Model routing:** Per-stage models via `MODEL_*` env vars; defaults all Gemini
  `gemini-3.5-flash-lite` (strict schema); stage-level overrides in `BatchConfig.model_overrides`
- **Confidence thresholds:** Configurable per stage, default 0.7-0.8
- **Prompt versioning:** Every prompt hashed, stored with results
- **Deterministic validation:** Use Python/SymPy where possible (V2), LLM-assisted V1

### 6.3 Data Constraints
- **Provenance on every field:** Source, model, prompt version, timestamp
- **Content hash:** SHA256 of normalized question for deduplication
- **Immutable logs:** Every stage logged with input/output snapshots
- **Versioning:** Schema, taxonomy, prompts, models, methodology all versioned

## 7. Security Requirements

| Requirement | Implementation |
|-------------|----------------|
| API Keys | Environment variables, never in code/logs |
| Prompt Injection | Sanitize input text, use structured outputs, limit context |
| File Uploads | Validate MIME type, size limit (10MB), sandbox parsing |
| Access Control | API key header (V1), OAuth/JWT (V2) |
| PII | Assume no PII in questions; if present, redact before logging |

## 8. Quality Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| Classification Accuracy | >90% | Gold standard eval |
| Difficulty Correlation | >0.8 | Expert rating correlation |
| Solution Correctness | >95% | Validation layer + gold standard |
| Formula Identification | >95% | Known formula recall |
| Silent Failure Rate | 0% | All errors explicit |
| Processing Cost | <$0.05/q | Token tracking at 10K scale |
| P95 Latency | <30s | Per question (async) |
| Batch Resume | <1min | From checkpoint |

## 9. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Reliability** | Checkpoint every 10 questions, 3 retries with exponential backoff |
| **Observability** | Structured logs, Prometheus metrics, cost tracking per question |
| **Extensibility** | Protocol interfaces, versioned taxonomy/prompts, pluggable models |
| **Reproducibility** | Full prompt/model/config snapshots with every output |
| **Auditability** | Immutable processing log, content hashes, provenance fields |

## 10. Important Decisions

| Decision | Rationale |
|----------|-----------|
| Single service V1 | Avoid distributed complexity; split when proven necessary |
| Protocol-based modules | Enables unit testing, model swaps, clear contracts |
| Structured LLM outputs | Eliminates parsing failures, type-safe downstream |
| File-based checkpoints | No Redis dependency, survives crashes, debuggable |
| 7-layer validation | Defense in depth; different layers catch different errors |
| Defer deterministic math | V1 speed; add SymPy in V2 when validation gaps measured |
| JSONL output | Streamable, line-delimited, easy for downstream consumers |
| Gemini free tier default | $0 dev/eval; strict structured output; Groq/OpenAI fallbacks stay one config change |
| Taxonomy in YAML + DB | Human-editable seed, versioned in DB, hot-reloadable |

## 11. Getting Started (For Implementation Agent)

### 11.1 Environment Setup
```bash
# Clone and setup
git clone <repo>
cd aptitude-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env: GEMINI_API_KEY (free tier: https://aistudio.google.com/apikey, no card)
# or set QME_LLM_PROVIDER=groq|openai + GROQ_API_KEY|OPENAI_API_KEY

# Run dev
make dev  # Starts docker-compose.dev.yml
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 11.2 Key Commands
```bash
make test          # Run all tests
make lint          # Ruff + MyPy
make eval          # Run gold standard evaluation
make build         # Build Docker image
qme --help         # CLI help
```

### 11.3 First Implementation Task
Start with **Step 1: Project Skeleton** (IMPLEMENTATION_ORDER.md)
- Create `pyproject.toml` with all dependencies
- Define all Pydantic models in `core/models.py`
- Define all Protocols in `core/protocols.py`
- Create FastAPI app with `/health` endpoint
- Create Typer CLI with `ingest` and `process` commands (stubs)
- Verify: `make test` passes, `docker compose up` works

## 12. Testing Strategy

### 12.1 Test Types
- **Unit:** Pure logic, no LLM (normalizer, difficulty calc, validators)
- **Integration:** Full pipeline with mocked LLM gateway
- **AI Evaluation:** Real LLM calls against gold standard dataset
- **Failure:** Malformed input, API errors, invalid JSON
- **Regression:** Prompt/model change detection

### 12.2 Gold Standard Dataset
Location: `tests/ai_evaluation/gold_standard/`
- `questions.jsonl` - 200 manually labeled questions
- `expected_outputs.jsonl` - Ground truth enriched questions

### 12.3 Running Evaluations
```bash
# Full evaluation
python scripts/run_evaluation.py

# Specific module
pytest tests/ai_evaluation/test_classification_accuracy.py -v
```

## 13. Cost Control Strategy

| Technique | Implementation |
|-----------|----------------|
| Model routing | Per-stage `MODEL_*` config (defaults: Gemini free tier, $0) |
| Structured outputs | Eliminate retries from parsing failures |
| Batch API | 50% discount for non-urgent batches (V2) |
| Prompt caching | Exact prompt hash cache (V2) |
| Token limits | Max tokens per stage configured |
| Cost tracking | Per-question USD estimate in output |

## 14. Files to Create First (Priority Order)

1. `pyproject.toml` - Dependencies
2. `src/qme/config/settings.py` - Settings
3. `src/qme/core/constants.py` - Enums
4. `src/qme/core/models.py` - All Pydantic models
5. `src/qme/core/protocols.py` - Protocol interfaces
6. `src/qme/main.py` - FastAPI app
7. `src/qme/cli.py` - Typer CLI
8. `docker/Dockerfile` - Container
9. `docker/docker-compose.yml` - Local dev
10. `data/taxonomy/seed_taxonomy.yaml` - Seed taxonomy
11. `config/prompts/classifier_v1.txt` - First prompt

## 15. Common Pitfalls to Avoid

| Pitfall | Prevention |
|---------|------------|
| Free-form LLM parsing | Always use `response_format` with Pydantic model |
| Silent failures | Every exception logged with context, status set explicitly |
| Hardcoded taxonomy | Load from YAML, version in DB, hot-reload support |
| Missing provenance | Auto-populate in base model `__init__` or factory |
| Cost surprises | Track tokens at every LLM call, alert on daily budget |
| Prompt drift | Version every prompt, hash stored with results |
| Schema drift | Single Pydantic model source of truth for JSONL/DB/API |
| Unreproducible runs | Snapshot config + prompts + model versions per batch |
