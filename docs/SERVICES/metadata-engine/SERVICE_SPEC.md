# Service Specification: metadata-engine

## Service Overview
**Purpose:** Transform raw aptitude questions into structured, validated, metadata-rich question objects.

**Responsibilities:**
- Ingest questions from multiple formats (JSONL, CSV, TXT, PDF, DOCX)
- Extract and normalize question content
- Classify into hierarchical taxonomy (category -> topic -> subtopic)
- Score difficulty using multi-factor model
- Extract or generate step-by-step solutions
- Identify formulas and link to future Formula KB
- Validate through 7-layer validation pipeline
- Track full provenance and processing metadata
- Output JSONL with complete enriched questions
- Manage batch processing with checkpointing
- Expose REST API and CLI

**Business Ownership:** Data Engineering / ML Engineering

## Service Boundaries
**Owns:**
- Question processing pipeline
- Taxonomy (categories, topics, subtopics)
- Prompts and model configurations
- Validation rules and thresholds
- Batch orchestration and checkpointing
- Output formats and schemas

**Never Owns:**
- Student data or user accounts
- Test generation or scheduling
- Question deduplication
- Payment/billing systems
- Authentication/authorization (beyond API keys)
- Real-time student-facing features

## Data Ownership
**Entities Owned:**
- EnrichedQuestion (core output)
- TaxonomyNode (hierarchical classification)
- ProcessingRun (batch tracking)
- Prompt (versioned templates)
- ReviewItem (human review queue)

**Relationships Owned:**
- Question -> TaxonomyNode (many-to-one: category, topic, subtopic)
- Question -> ProcessingRun (many-to-one)
- Question -> Prompt (many-to-one per stage)
- ProcessingRun -> Questions (one-to-many)

## Dependencies
**Internal:** None (single service V1)

**External:**
- OpenAI API (LLM provider) - required
- PostgreSQL + pgvector (V2+) - optional for V1
- File storage (local volume) - required
- Nginx (reverse proxy) - production only

## Communication
**APIs Exposed:**
- REST (FastAPI): /api/v1/questions/process, /api/v1/batches/*, /api/v1/health, /api/v1/metrics
- CLI: qme ingest, qme process, qme review, qme eval

**Events Produced (V2+):**
- BatchComplete: {batch_id, status, counts, cost}
- QuestionFailed: {question_id, error, stage}
- ReviewNeeded: {question_id, reason_codes}

**Events Consumed:** None (pull-based input)

## Security Requirements
**Authentication:** API key header (V1), OAuth/JWT (V2)
**Authorization:** Role-based (admin, processor, reviewer)
**Data Protection:**
- No PII in questions (assumed)
- API keys in environment variables / secret manager
- Input sanitization for prompt injection
- File type validation, size limits (10MB)
- TLS termination at Nginx

**Prompt Injection Prevention:**
- Sanitize all user text before embedding in prompts
- Use structured outputs (no free-form parsing)
- Limit context window per request
- Monitor for anomalous prompt patterns

## Observability Requirements
**Logging:**
- Structured JSON (structlog)
- Correlation IDs across request/batch/question
- Levels: DEBUG (dev), INFO (prod), ERROR (always)
- Fields: timestamp, level, service, batch_id, question_id, stage, duration_ms, tokens, cost

**Metrics (Prometheus):**
- API: request_rate, latency_p50/p95/p99, error_rate
- Batch: questions_processed_total, success_rate, review_rate, failure_rate
- LLM: tokens_per_question, cost_per_question, model_distribution
- System: cpu, memory, disk, network

**Tracing:** OpenTelemetry ready (V2)

**Alerts (V2):**
- API down (health check fails 3x)
- Batch failure rate >10% in 1hr
- Cost spike >2x baseline daily
- Disk space >80%
- Review queue backlog >100 items
