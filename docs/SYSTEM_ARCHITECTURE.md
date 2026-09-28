# System Architecture: Question Metadata Engine

## 1. High-Level Architecture

`
+---------------------------------------------------------------------------------+
|                        QUESTION METADATA ENGINE                                 |
+---------------------------------------------------------------------------------+
|                                                                                 |
|  +----------+    +------------------+    +----------------------------------+  |
|  |  Input   |--->|  Extraction &    |--->|     Core Pipeline (Async)        |  |
|  | Sources  |    |  Cleaning        |    |                                  |  |
|  +----------+    +------------------+    |  +----------------------------+  |  |
|       |                                    |  | Question Classifier        |  |  |
|       v                                    |  |   (Topic/Subtopic)         |  |  |
|  +--------------------------------------+  |  +----------------------------+  |  |
|  |      Batch Coordinator               |  |  | Difficulty Engine          |  |  |
|  |  (Checkpoint, Retry, Progress)       |  |  +----------------------------+  |  |
|  +--------------------------------------+  |  | Solution Engine              |  |  |
|       |                                    |  |  (Extract / Generate)      |  |  |
|       v                                    |  +----------------------------+  |  |
|  +--------------------------------------+  |  | Formula Extractor          |  |  |
|  |      Validation Pipeline             |  |  +----------------------------+  |  |
|  |  (Schema, Answer, Calc, Consist)     |  |  | Validator (Multi-Layer)    |  |  |
|  +--------------------------------------+  |  +----------------------------+  |  |
|       |                                    |                                  |  |
|       v                                    +----------------------------------+  |
|  +--------------------------------------+                   |                   |
|  |      Output Generator                |                   v                   |
|  |  (JSONL, Provenance, Metrics)        |          +------------------+       |
|  +--------------------------------------+          |  LLM Gateway     |       |
|                                                    |  (OpenAI Client) |       |
|                                                    +------------------+       |
|                                                           |                 |
|                                                    +------+------+         |
|                                                    |             |         |
|                                            +-----------+  +-----------+    |
|                                            | GPT-4o    |  | GPT-4o    |    |
|                                            | (complex) |  |-mini (fast)|   |
|                                            +-----------+  +-----------+    |
+---------------------------------------------------------------------------------+
                              |
                              v
+---------------------------------------------------------------------------------+
|                      DOWNSTREAM CONSUMERS                                       |
|  +-----------------+  +-----------------+  +---------------------------------+  |
|  | Deduplication   |  |  Evaluation/    |  |  Human Review                 |  |
|  | Engine          |  |  QA Team        |  |  Queue                        |  |
|  +-----------------+  +-----------------+  +---------------------------------+  |
+---------------------------------------------------------------------------------+
`

## 2. Component Breakdown

### 2.1 Input Layer
| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| FileIngestor | Parse PDF, DOCX, TXT, CSV, JSONL | ingest(file_path) -> List[RawQuestion] |
| ManualInputHandler | Accept single question via API | submit(question_dict) -> RawQuestion |
| SourceTracker | Attach provenance metadata | track(source_info) -> Provenance |

### 2.2 Extraction & Cleaning
| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| TextExtractor | Extract text from binary formats | extract(file_bytes, mime_type) -> str |
| QuestionParser | Parse raw text into structured fields | parse(raw_text, format_hint) -> ParsedQuestion |
| Normalizer | Clean text, standardize formatting | normalize(parsed) -> NormalizedQuestion |

### 2.3 Core AI Pipeline (Pluggable Modules)
Each module implements a standard interface for replaceability:

`python
class QuestionClassifier(Protocol):
    async def classify(self, question: NormalizedQuestion) -> ClassificationResult

class DifficultyEngine(Protocol):
    async def score(self, question: NormalizedQuestion, classification: ClassificationResult) -> DifficultyResult

class SolutionEngine(Protocol):
    async def solve(self, question: NormalizedQuestion, classification: ClassificationResult) -> SolutionResult

class FormulaExtractor(Protocol):
    async def extract(self, question: NormalizedQuestion, solution: SolutionResult) -> FormulaResult

class Validator(Protocol):
    async def validate(self, enriched: EnrichedQuestion) -> ValidationResult
`

### 2.4 Validation Pipeline (Multi-Layer)
| Layer | Checks | Action on Failure |
|-------|--------|-------------------|
| Schema | Pydantic model compliance | Reject, log, mark failed |
| Answer | Option matching, type correctness | Flag needs_review |
| Calculation | Deterministic verification (V2: SymPy) | Flag needs_review |
| Formula Consistency | Formulas match solution steps | Flag needs_review |
| Solution-Answer | Solution derives correct answer | Flag needs_review |
| Metadata Consistency | Topic aligns with concepts, difficulty matches steps | Flag needs_review |
| Confidence | LLM confidence thresholds | Flag needs_review if low |

### 2.5 Batch Coordinator
- Checkpointing: Write progress every N questions (configurable, default 10)
- Retry Logic: Exponential backoff (1s, 2s, 4s, max 3 retries)
- Partial Failure: Continue on individual question failure, aggregate results
- Rate Limiting: Token bucket per model (respect OpenAI limits)
- Cost Tracking: Accumulate token usage, estimate USD cost

### 2.6 Output Layer
| Component | Responsibility |
|-----------|---------------|
| JSONLWriter | Stream write enriched questions to .jsonl |
| MetricsCollector | Aggregate processing stats, token usage, costs |
| ReviewQueue | Export flagged questions for human review |

### 2.7 LLM Gateway
- Model Router: Select model per task (4o-mini vs 4o)
- Structured Output: Enforce JSON schema via response_format
- Prompt Versioning: Hash prompts, store with results
- Error Handling: Parse failures, rate limits, context windows
- Caching (V2): Exact prompt cache with TTL

## 3. Data Flow

### 3.1 Single Question Flow

Raw Input
    |
    v
+---------------------+
| Extract & Clean     | ---> NormalizedQuestion
| (Parser + Normalizer)|      (text, options, answer, source)
+---------------------+
    |
    v
+---------------------+
| Question Classifier | ---> ClassificationResult
| (Topic, Subtopic,   |      (category, topic, subtopic,
|  Concepts, Type,    |       concepts, confidence)
|  Tags)              |
+---------------------+
    |
    v
+---------------------+
| Difficulty Engine   | ---> DifficultyResult
| (Multi-factor      |      (score 0-10, rating, factors,
|  scoring model)     |       estimated_time, confidence)
+---------------------+
    |
    v
+---------------------+
| Solution Engine     | ---> SolutionResult
| (Extract existing   |      (steps, formulas, calculations,
|  OR generate new)   |       final_answer, source, confidence)
+---------------------+
    |
    v
+---------------------+
| Formula Extractor   | ---> FormulaResult
| (Identify formulas  |      (name, expression, category,
|  from solution)     |       reference_id, confidence)
+---------------------+
    |
    v
+---------------------+
| Validation Pipeline | ---> ValidationResult
| (7 layers)          |      (status, errors, warnings, flags)
+---------------------+
    |
    v
+---------------------+
| Output Generator    | ---> EnrichedQuestion (JSON)
| (Assemble +         |      (all above + provenance +
|  Provenance +       |       processing_metadata)
|  Versioning)        |
+---------------------+

### 3.2 Batch Flow

Batch File (JSONL/CSV/PDF)
    |
    v
+---------------------+
| Batch Coordinator   |
| - Load checkpoint   |
| - Iterate questions |
| - Process each      |
| - Checkpoint save   |
| - Handle retries    |
+---------------------+
    |
    v
+---------------------+
| Output Files        |
| - output.jsonl      |  (all successful)
| - failed.jsonl      |  (failed with error context)
| - review.jsonl      |  (needs_review items)
| - metrics.json      |  (aggregate stats)
+---------------------+

## 4. Service Decomposition

For V1, the engine runs as a SINGLE deployable service with internal modularity.
Future phases may split into microservices:

| Future Service | Ownership | Trigger for Split |
|----------------|-----------|-------------------|
| classification-service | Topic/Difficulty | Independent scaling, different models |
| solution-service | Solution gen/validation | GPU/heavy compute isolation |
| formula-service | Formula KB linking | Dedicated formula team |
| batch-orchestrator | Coordination | Multi-tenant, priority queues |

V1 Decision: Single service, modular internals. Split when proven necessary.

## 5. Interface Definitions

### 5.1 Internal Module Interfaces (Python Protocols)
All AI modules follow the Protocol pattern for:
- Testability (mock implementations)
- Replaceability (swap LLM for fine-tuned model)
- Clear contracts (input/output types)

### 5.2 External API (FastAPI)

POST   /api/v1/questions/process      # Single question
POST   /api/v1/batches                # Submit batch job
GET    /api/v1/batches/{id}           # Batch status
GET    /api/v1/batches/{id}/results   # Download results
GET    /api/v1/batches/{id}/review    # Get review queue
GET    /api/v1/health                 # Health check
GET    /api/v1/metrics                # Prometheus metrics

### 5.3 CLI Interface

qme ingest --input file.jsonl --output results/
qme process --input file.jsonl --output results/ --checkpoint-dir .checkpoints
qme review --input review.jsonl --action approve|reject|edit
qme eval --gold-standard gold.jsonl --predictions pred.jsonl

## 6. Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.11+ |
| Web Framework | FastAPI | 0.110+ |
| Validation | Pydantic | v2 |
| Async HTTP | httpx / openai | latest |
| Config | pydantic-settings | latest |
| Logging | structlog | latest |
| Metrics | prometheus-client | latest |
| CLI | typer | latest |
| Testing | pytest, pytest-asyncio | latest |
| Container | Docker | 24+ |
| Deployment | Docker Compose | v2 |

## 7. Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| Single service V1 | Simplicity, no distributed system complexity, easy debugging |
| Protocol-based modules | Enables unit testing, future model swaps, clear boundaries |
| Structured LLM outputs | No parsing failures, type safety, downstream reliability |
| File-based checkpointing | No Redis dependency, survives restarts, simple debugging |
| Multi-layer validation | Defense in depth, catch different error classes |
| Provenance on every field | Auditability, reprocessing, debugging |
| Defer deterministic math | V1 speed, add SymPy in V2 when validation gaps measured |
| JSONL output | Streamable, line-delimited, easy for downstream consumers |
