# Feature to Service Mapping: Question Metadata Engine

## 1. Service Overview

For V1, the Question Metadata Engine is a **single service** with internal modularity.
All features map to this single service.

**Service Name:** `metadata-engine`
**Service Type:** Backend AI Pipeline Service
**Deployment:** Single container (FastAPI + batch worker)

## 2. Feature Mapping Table

| Feature ID | Feature Name | Owning Service | Module(s) | Status |
|------------|--------------|----------------|-----------|--------|
| FE-001 | Question Extraction & Normalization | metadata-engine | `ingestion/` | V1 Core |
| FE-002 | Topic/Subtopic Classification | metadata-engine | `pipeline/stages/classifier.py` | V1 Core |
| FE-003 | Difficulty Scoring | metadata-engine | `pipeline/stages/difficulty.py` | V1 Core |
| FE-004 | Solution Engine | metadata-engine | `pipeline/stages/solution.py` | V1 Core |
| FE-005 | Formula Identification | metadata-engine | `pipeline/stages/formula.py` | V1 Core |
| FE-006 | Multi-Layer Validation | metadata-engine | `validation/` | V1 Core |
| FE-007 | Batch Processing Pipeline | metadata-engine | `pipeline/coordinator.py`, `pipeline/checkpoint.py` | V1 Core |
| FE-008 | Source Tracking & Versioning | metadata-engine | `ingestion/source_tracker.py`, `core/models.py` | V1 Core |
| FE-009 | Human Review Workflow | metadata-engine | `output/review_queue.py`, `api/routes/batches.py` | V1 Core |
| FE-010 | Observability & Cost Tracking | metadata-engine | `llm/cost_tracker.py`, `output/metrics_collector.py`, `api/routes/metrics.py` | V1 Core |

## 3. Service Specification

### 3.1 metadata-engine Service

**Purpose:** Transform raw aptitude questions into structured, validated, metadata-rich question objects.

**Responsibilities:**
- Ingest questions from multiple formats (JSONL, CSV, TXT, PDF, DOCX)
- Extract and normalize question content
- Classify into hierarchical taxonomy (category → topic → subtopic)
- Score difficulty using multi-factor model
- Extract or generate step-by-step solutions
- Identify formulas and link to future Formula KB
- Validate through 7-layer validation pipeline
- Track full provenance and processing metadata
- Output JSONL with complete enriched questions
- Manage batch processing with checkpointing
- Expose REST API and CLI

**Business Ownership:** Data Engineering / ML Engineering

**Service Boundaries:**
- **Owns:** Question processing pipeline, taxonomy, prompts, validation rules
- **Never Owns:** Student data, test generation, deduplication, payments, user auth

**Data Ownership:**
- Entities: EnrichedQuestion, TaxonomyNode, ProcessingRun, Prompt, ReviewItem
- Relationships: Question → Taxonomy (many-to-one), Question → ProcessingRun (many-to-one)

**Dependencies:**
- **Internal:** None (single service V1)
- **External:** OpenAI API (LLM), PostgreSQL (V2+), File storage (input/output)

**Communication:**
- **APIs Exposed:** REST (FastAPI) + CLI
- **Events Produced:** BatchComplete, QuestionFailed, ReviewNeeded (via webhooks V2)
- **Events Consumed:** None (pull-based input)

**Security Requirements:**
- Authentication: API key header (V1: simple, V2: OAuth/JWT)
- Authorization: Role-based (admin, processor, reviewer)
- Data Protection: No PII in questions, API keys in secrets
- Input Sanitization: Prompt injection prevention, file type validation

**Observability Requirements:**
- Logging: Structured JSON (structlog), correlation IDs
- Metrics: Prometheus (/metrics endpoint)
- Tracing: OpenTelemetry ready (V2)
- Alerts: Failure rate >5%, cost spike >2x, queue backlog

## 4. Future Service Decomposition (V2+)

When scale or team structure demands, split into:

| Service | Features | Trigger |
|---------|----------|---------|
| `classification-service` | FE-002, FE-003 | Independent model scaling, different GPU needs |
| `solution-service` | FE-004, FE-005, FE-006 | Heavy compute, GPU isolation, formula KB coupling |
| `batch-orchestrator` | FE-007, FE-009 | Multi-tenant, priority queues, scheduling |
| `ingestion-service` | FE-001, FE-008 | Document processing, OCR, format expansion |

## 5. Ownership Matrix

| Component | Owner Team | Reviewer |
|-----------|------------|----------|
| Taxonomy | Content/ML | Data Eng |
| Prompts | ML Engineering | Content |
| Validation Rules | ML + Platform | QA |
| Pipeline Orchestration | Platform | ML |
| API/CLI | Platform | All |
| Evaluation Harness | ML | Content |
