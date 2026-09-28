# Implementation Order: Question Metadata Engine

## 1. Ordering Principles

1. **Dependency Order** - Build what others depend on first
2. **Risk Reduction** - Tackle highest uncertainty early
3. **Incremental Value** - Each step produces usable output
4. **Testability** - Validate before building on top

## 2. Detailed Implementation Sequence

### Step 1: Project Skeleton (Day 1-2)
**Files to Create:**
- `pyproject.toml` - Dependencies, tool config
- `src/qme/__init__.py` - Package init
- `src/qme/config/settings.py` - Pydantic settings
- `src/qme/core/models.py` - All Pydantic models
- `src/qme/core/protocols.py` - Protocol interfaces
- `src/qme/core/constants.py` - Enums, constants
- `src/qme/main.py` - FastAPI app factory
- `src/qme/cli.py` - Typer CLI skeleton
- `docker/Dockerfile` - Multi-stage build
- `docker/docker-compose.yml` - Local dev
- `.env.example` - Env template
- `Makefile` - Common commands

**Tests:** Import tests, model validation tests

**Why First:** Everything depends on models and config. Validates tech stack works.

---

### Step 2: Ingestion Core (Day 3-5)
**Files to Create:**
- `src/qme/ingestion/ingestor.py` - Base + factory
- `src/qme/ingestion/parsers/jsonl_parser.py`
- `src/qme/ingestion/parsers/csv_parser.py`
- `src/qme/ingestion/parsers/txt_parser.py`
- `src/qme/ingestion/normalizer.py`
- `src/qme/ingestion/source_tracker.py`
- `data/samples/sample_questions.jsonl`

**Tests:** Parser unit tests, normalizer tests, sample ingestion

**Why Second:** Need real normalized questions to test downstream stages.

---

### Step 3: Taxonomy & Classification (Day 6-10)
**Files to Create:**
- `data/taxonomy/seed_taxonomy.yaml` - Hierarchical taxonomy
- `src/qme/config/taxonomy_loader.py` - Load + version
- `src/qme/config/prompts/classifier_v1.txt`
- `src/qme/pipeline/stages/classifier.py` - QuestionClassifier impl
- `src/qme/llm/gateway.py` - LLMGateway with model routing
- `src/qme/llm/structured_output.py` - Schema enforcement
- `src/qme/llm/prompt_manager.py` - Versioned prompts
- `tests/ai_evaluation/gold_standard/classification.jsonl`

**Tests:** Classification accuracy eval, structured output parsing

**Why Third:** Classification is first AI stage; taxonomy design affects everything downstream.

---

### Step 4: Difficulty Engine (Day 11-14)
**Files to Create:**
- `src/qme/config/prompts/difficulty_v1.txt`
- `src/qme/pipeline/stages/difficulty.py` - DifficultyEngine impl
- Factor calculation logic (pure functions in `utils/`)
- `tests/ai_evaluation/gold_standard/difficulty.jsonl`

**Tests:** Difficulty factor unit tests, correlation eval

**Why Fourth:** Depends on classification output; pure logic + LLM, testable in isolation.

---

### Step 5: Solution Engine (Day 15-21)
**Files to Create:**
- `src/qme/config/prompts/solution_v1.txt` (generate)
- `src/qme/config/prompts/solution_extract_v1.txt` (extract)
- `src/qme/pipeline/stages/solution.py` - SolutionEngine impl
- `src/qme/validation/solution_validator.py` - Solution→answer check
- `tests/ai_evaluation/gold_standard/solutions.jsonl`

**Tests:** Solution correctness eval, extraction tests

**Why Fifth:** Most complex LLM task; highest risk of hallucination; needs validation.

---

### Step 6: Formula Extraction (Day 22-25)
**Files to Create:**
- `src/qme/config/prompts/formula_v1.txt`
- `src/qme/pipeline/stages/formula.py` - FormulaExtractor impl
- Formula reference KB interface spec (for future)
- `tests/ai_evaluation/gold_standard/formulas.jsonl`

**Tests:** Formula identification accuracy

**Why Sixth:** Depends on solution output; simpler than solution generation.

---

### Step 7: Validation Pipeline (Day 26-30)
**Files to Create:**
- `src/qme/validation/schema_validator.py`
- `src/qme/validation/answer_validator.py`
- `src/qme/validation/calculation_validator.py` (LLM-assisted V1)
- `src/qme/validation/consistency_validator.py`
- `src/qme/validation/confidence_checker.py`
- `src/qme/pipeline/stages/validator.py` - Orchestrator
- `src/qme/output/review_queue.py`

**Tests:** Validation layer unit tests, integration with bad inputs

**Why Seventh:** Catches errors from all previous stages; must be comprehensive.

---

### Step 8: Pipeline Orchestration (Day 31-35)
**Files to Create:**
- `src/qme/pipeline/coordinator.py` - BatchCoordinator
- `src/qme/pipeline/checkpoint.py` - Checkpoint manager
- `src/qme/llm/cost_tracker.py` - Token/cost tracking
- `src/qme/output/jsonl_writer.py`
- `src/qme/output/metrics_collector.py`
- `src/qme/api/routes/questions.py` - Single question endpoint
- `src/qme/api/routes/batches.py` - Batch endpoints

**Tests:** Full pipeline integration, checkpoint/resume, batch API

**Why Eighth:** Connects all stages into runnable batch processor.

---

### Step 9: Document Parsers (Day 36-40)
**Files to Create:**
- `src/qme/ingestion/parsers/pdf_parser.py`
- `src/qme/ingestion/parsers/docx_parser.py`
- Format detection logic
- Sample PDF/DOCX in `data/samples/`

**Tests:** PDF/DOCX parsing accuracy

**Why Ninth:** Nice-to-have for V1; core pipeline works with JSONL.

---

### Step 10: PostgreSQL Integration (Day 41-45)
**Files to Create:**
- `alembic/` - Migration setup
- `alembic/versions/..._initial_schema.py` - From DATABASE_SCHEMA.md
- `src/qme/storage/` - Repository layer (optional, or direct SQL)
- `scripts/import_jsonl.py` - Batch import
- `src/qme/llm/embeddings.py` - Embedding generation

**Tests:** Roundtrip JSONL → DB → JSONL, vector search

**Why Tenth:** Downstream dependency (Deduplication Engine) needs DB.

---

### Step 11: Evaluation Harness (Day 46-50)
**Files to Create:**
- `src/qme/evaluation/metrics.py` - Accuracy, F1, correlation
- `src/qme/evaluation/runner.py` - Automated evaluation
- `src/qme/evaluation/gold_standard.py` - Dataset loader
- `tests/regression/test_prompt_changes.py`
- `scripts/run_evaluation.py`

**Tests:** Full evaluation suite, regression detection

**Why Eleventh:** Validates quality before production; catches regressions.

---

### Step 12: Polish & Documentation (Day 51-55)
**Files to Create/Update:**
- `README.md` - Complete usage guide
- `docs/AI_IMPLEMENTATION_GUIDE.md` - For implementation agents
- `docs/DEPLOYMENT_ARCHITECTURE.md` - Deployment guide
- Runbooks: scaling, troubleshooting, cost optimization
- CI/CD pipeline (GitHub Actions)

**Why Twelfth:** Production readiness.

---

## 3. Dependency Graph

```
Step 1 (Skeleton)
    │
    ├─→ Step 2 (Ingestion)
    │       │
    │       └─→ Step 3 (Classification) ←─ Step 4 (Difficulty)
    │               │
    │               └─→ Step 5 (Solution) ←─ Step 6 (Formulas)
    │                       │
    │                       └─→ Step 7 (Validation)
    │                               │
    │                               └─→ Step 8 (Orchestration)
    │                                       │
    │                                       ├─→ Step 9 (Documents)
    │                                       │
    │                                       └─→ Step 10 (PostgreSQL)
    │                                               │
    │                                               └─→ Step 11 (Evaluation)
    │                                                       │
    │                                                       └─→ Step 12 (Polish)
```

## 4. Parallelization Opportunities

| Can Run Parallel | Reason |
|------------------|--------|
| Steps 3 & 4 | Difficulty only needs classification output, can develop in parallel with mock classifier |
| Steps 5 & 6 | Formula extraction depends on solution, but interface can be defined early |
| Step 9 | Document parsers independent; can start after Step 2 |
| Step 11 | Evaluation harness can be built alongside phases, run at end |

## 5. Minimum Viable Milestones

| Milestone | Steps | Demo |
|-----------|-------|------|
| M1: Skeleton | 1 | `qme --help`, API health |
| M2: Ingestion | 1-2 | `qme ingest sample.jsonl` → normalized |
| M3: Classification | 1-3 | Single question → topic/subtopic |
| M4: Full Pipeline | 1-7 | Single question → fully enriched |
| M5: Batch Processing | 1-8 | 100 questions → JSONL outputs |
| M6: Production Ready | 1-12 | 10K questions, DB, eval passing |
