# Development Roadmap: Question Metadata Engine

## 1. Roadmap Overview

**Philosophy:** Incremental delivery. Each phase produces a runnable, testable system.
**Optimization:** Build One Service → Test → Debug → Deploy → Next

## 2. Phase Definitions

### Phase 1: Foundation (Weeks 1-2)
**Objective:** Runnable project skeleton with config, models, and basic CLI/API

**Deliverables:**
- Project structure per PROJECT_STRUCTURE.md
- Pydantic models (EnrichedQuestion, all intermediates)
- Protocol interfaces for all pipeline stages
- FastAPI app with health endpoint
- Typer CLI with ingest/process commands
- Docker Compose for local dev
- Settings management (pydantic-settings)
- Basic logging (structlog) and metrics (prometheus-client)

**Dependencies:** None

**Risks:**
- Over-engineering models before seeing real data
- **Mitigation:** Start with minimal fields, expand based on sample questions

**Validation Criteria:**
- `make test` passes
- `docker compose up` starts API
- `qme --help` shows commands
- Health endpoint returns 200

---

### Phase 2: Ingestion & Extraction (Weeks 2-3)
**Objective:** Parse raw inputs → NormalizedQuestion

**Deliverables:**
- FileIngestor base class + JSONL, CSV, TXT parsers
- QuestionParser for structured extraction
- Normalizer (clean text, standardize options, validate answer in options)
- SourceTracker (attach provenance)
- Unit tests for each parser
- Sample questions in data/samples/

**Dependencies:** Phase 1

**Risks:**
- PDF/DOCX parsing complexity
- **Mitigation:** Defer PDF/DOCX to Phase 9; V1 = JSONL/CSV/TXT only

**Validation Criteria:**
- Ingest sample.jsonl → output normalized questions
- CLI `qme ingest` works end-to-end
- Handles malformed input gracefully (logs error, continues)

---

### Phase 3: Taxonomy & Classification (Weeks 3-4)
**Objective:** Hierarchical topic classification with versioned taxonomy

**Deliverables:**
- Seed taxonomy (YAML) for Quantitative Aptitude
- Taxonomy loader with version tracking
- QuestionClassifier module (LLM-based, structured output)
- Prompt template v1 for classification
- GPT-4o-mini for classification (cost optimization)
- Confidence scoring + threshold config
- Gold standard evaluation set (50 questions)
- Evaluation script for classification accuracy

**Dependencies:** Phase 1, 2

**Risks:**
- Taxonomy design changes
- **Mitigation:** Version taxonomy from start, loader supports hot-reload

**Validation Criteria:**
- Classification accuracy >85% on gold standard
- Structured output never fails parsing
- Taxonomy version recorded in output

---

### Phase 4: Difficulty Engine (Weeks 4-5)
**Objective:** Multi-factor difficulty scoring (0-10 scale)

**Deliverables:**
- DifficultyEngine module
- Factor definitions: concept_count, reasoning_complexity, calculation_complexity, steps, ambiguity, formula_complexity
- Weighted scoring algorithm (configurable weights)
- Difficulty rating buckets: easy (0-3.5), medium (3.5-6.5), hard (6.5-10)
- Estimated time model (base + factor adjustments)
- Prompt template v1 for difficulty
- Evaluation against expert ratings (correlation >0.7)

**Dependencies:** Phase 3

**Risks:**
- Subjective difficulty factors
- **Mitigation:** Explicit factor definitions, calibration set, versioned methodology

**Validation Criteria:**
- Score distribution matches expectations
- Factor contributions explainable
- Correlation >0.7 with expert ratings on eval set

---

### Phase 5: Solution Engine (Weeks 5-7)
**Objective:** Extract existing solutions OR generate step-by-step solutions

**Deliverables:**
- SolutionEngine module with two modes:
  - Extract: Parse source-provided solution
  - Generate: LLM creates solution from scratch
- Step structure: description, formula_refs, calculation, result
- GPT-4o for generation (complex reasoning)
- GPT-4o-mini for extraction
- Solution validation (does it derive correct answer?)
- Prompt templates v1 for both modes
- Confidence scoring

**Dependencies:** Phase 3, 4

**Risks:**
- Hallucinated solutions
- **Mitigation:** Validation layer (Phase 6), confidence thresholds, flag for review

**Validation Criteria:**
- Generated solutions correct >90% on eval set
- Extracted solutions normalized consistently
- Confidence correlates with correctness

---

### Phase 6: Formula Extraction (Weeks 6-7)
**Objective:** Identify formulas from solution, output references

**Deliverables:**
- FormulaExtractor module
- Formula reference format: name, expression, category, reference_id
- Handle unknown formulas (not in future KB) → flag for review
- Prompt template v1
- Integration with SolutionEngine output

**Dependencies:** Phase 5

**Risks:**
- Formula naming inconsistency
- **Mitigation:** Standardized categories, reference_id for KB linking

**Validation Criteria:**
- Known formulas identified >95%
- Unknown formulas flagged explicitly
- Output format matches Formula KB interface spec

---

### Phase 7: Validation Pipeline (Weeks 7-8)
**Objective:** 7-layer validation with explicit pass/fail/review

**Deliverables:**
- Schema validation (Pydantic)
- Answer validation (option matching, type)
- Calculation validation (V1: LLM-assisted, V2: SymPy)
- Formula consistency (formulas match solution steps)
- Solution-answer consistency (solution derives answer)
- Metadata consistency (topic aligns with concepts)
- Confidence threshold checking
- ValidationResult with status: validated/needs_review/failed
- Review queue export

**Dependencies:** Phases 3-6

**Risks:**
- Validation too strict → high review queue
- Validation too loose → bad data downstream
- **Mitigation:** Configurable thresholds, monitor review rate, tune per layer

**Validation Criteria:**
- Zero silent failures (all errors explicit)
- Review rate <10% on clean data
- Known bad inputs caught and flagged

---

### Phase 8: Batch Processing & Checkpointing (Weeks 8-9)
**Objective:** Reliable batch processing of 1K-10K questions

**Deliverables:**
- BatchCoordinator with:
  - Checkpoint every N questions (configurable)
  - Resume from checkpoint
  - Retry logic (exponential backoff, max 3)
  - Rate limiting (token bucket per model)
  - Cost tracking (tokens → USD)
  - Partial failure handling (continue on error)
- Progress reporting (tqdm-style CLI, API status)
- Output files: output.jsonl, failed.jsonl, review.jsonl, metrics.json
- Processing run metadata in output

**Dependencies:** Phases 1-7

**Risks:**
- Checkpoint corruption
- **Mitigation:** Atomic writes, validate on resume, backup checkpoints

**Validation Criteria:**
- Process 1000 questions end-to-end
- Kill/resume mid-batch → no data loss, no reprocessing
- Rate limits respected
- Cost tracking accurate within 10%

---

### Phase 9: Document Ingestion (Weeks 9-10)
**Objective:** Support PDF and DOCX input formats

**Deliverables:**
- PDF parser (pdfplumber/pymupdf)
- DOCX parser (python-docx)
- Text extraction quality validation
- Format detection from file extension/MIME
- Integration with existing ingestion pipeline

**Dependencies:** Phase 2

**Risks:**
- Poor text extraction from scanned PDFs
- **Mitigation:** Detect image-only PDFs, flag for OCR (V2), manual review

**Validation Criteria:**
- Parse sample PDF/DOCX → same normalized output as JSONL
- Extraction accuracy >95% on clean digital documents

---

### Phase 10: Output, Storage & Integration (Weeks 10-11)
**Objective:** Production-ready output and PostgreSQL integration

**Deliverables:**
- JSONL streaming writer (memory efficient)
- PostgreSQL schema migration (alembic)
- Batch import script (JSONL → PostgreSQL)
- pgvector embedding generation (text-embedding-3-small)
- HNSW index creation
- Deduplication Engine interface spec (for downstream team)

**Dependencies:** Phase 8

**Risks:**
- Schema drift between JSONL and DB
- **Mitigation:** Single Pydantic model source of truth, auto-generate migrations

**Validation Criteria:**
- JSONL → PostgreSQL roundtrip preserves all fields
- Embeddings generated for all questions
- Vector search returns relevant results

---

### Phase 11: Evaluation & Optimization (Weeks 11-12)
**Objective:** Measure quality, optimize cost/latency

**Deliverables:**
- Full evaluation harness (classification, difficulty, solution, formula)
- Gold standard dataset (200 questions)
- Regression test suite for prompt/model changes
- Cost optimization: batch API, prompt caching, model routing
- Latency optimization: async pipeline, connection pooling
- Documentation: runbooks, troubleshooting, scaling guide

**Dependencies:** All previous phases

**Risks:**
- Evaluation metrics not actionable
- **Mitigation:** Define clear pass/fail criteria per metric

**Validation Criteria:**
- Classification accuracy >90%
- Difficulty correlation >0.8
- Solution correctness >95%
- Cost <$0.05/question at 10K scale
- P95 latency <30s/question

## 3. Phase Summary Table

| Phase | Weeks | Focus | Key Output |
|-------|-------|-------|------------|
| 1 | 1-2 | Foundation | Runnable skeleton |
| 2 | 2-3 | Ingestion | JSONL/CSV/TXT → Normalized |
| 3 | 3-4 | Classification | Topic/Subtopic + Taxonomy |
| 4 | 4-5 | Difficulty | 0-10 score + factors |
| 5 | 5-7 | Solutions | Extract/Generate + validate |
| 6 | 6-7 | Formulas | Formula refs + KB interface |
| 7 | 7-8 | Validation | 7-layer pipeline |
| 8 | 8-9 | Batch | Checkpointed 10K processing |
| 9 | 9-10 | Documents | PDF/DOCX support |
| 10 | 10-11 | Storage | PostgreSQL + pgvector |
| 11 | 11-12 | Evaluation | Quality metrics + optimization |

## 4. Milestone Gates

Each phase must pass before next begins:
1. All unit tests pass
2. Integration test for phase scope passes
3. No critical bugs open
4. Documentation updated
5. Code reviewed (self-review for AI agent)
