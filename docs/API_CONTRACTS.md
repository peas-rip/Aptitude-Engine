# API Contracts: Question Metadata Engine

## 1. External REST API (FastAPI)

### 1.1 Single Question Processing
```
POST /api/v1/questions/process
```

**Request:**
```json
{
  "question_text": "A train travels at 54 km/hr...",
  "options": {"A": "20s", "B": "24s", "C": "28s", "D": "32s"},
  "correct_answer": "B",
  "source": {
    "name": "Quantitative Aptitude by R.S. Aggarwal",
    "type": "pdf",
    "identifier": "ISBN-9789352534029",
    "page": 142,
    "question_id": "Ex-12-Q15"
  },
  "options": {
    "generate_solution": true,
    "extract_formulas": true,
    "validate": true
  }
}
```

**Response (200):**
```json
{
  "question_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "validated",
  "result": { /* Full EnrichedQuestion object */ },
  "processing_time_ms": 12500,
  "token_usage": {"prompt": 1200, "completion": 800, "total": 2000},
  "estimated_cost_usd": 0.005
}
```

**Response (202 - Async):**
```json
{
  "task_id": "task-uuid",
  "status": "processing",
  "poll_url": "/api/v1/tasks/task-uuid"
}
```

### 1.2 Batch Processing
```
POST /api/v1/batches
```

**Request (multipart/form-data):**
- `file`: JSONL/CSV/TXT/PDF/DOCX file
- `config`: JSON config (optional)

**Response (202):**
```json
{
  "batch_id": "batch-uuid",
  "status": "queued",
  "status_url": "/api/v1/batches/batch-uuid",
  "results_url": "/api/v1/batches/batch-uuid/results",
  "review_url": "/api/v1/batches/batch-uuid/review"
}
```

### 1.3 Batch Status
```
GET /api/v1/batches/{batch_id}
```

**Response:**
```json
{
  "batch_id": "batch-uuid",
  "status": "running",
  "progress": {
    "total": 1000,
    "processed": 427,
    "successful": 410,
    "failed": 12,
    "needs_review": 5
  },
  "started_at": "2026-09-28T10:00:00Z",
  "estimated_completion": "2026-09-28T14:30:00Z",
  "total_tokens": 854000,
  "estimated_cost_usd": 2.15
}
```

### 1.4 Batch Results
```
GET /api/v1/batches/{batch_id}/results?format=jsonl&status=all
```

**Response:** Stream JSONL file (application/x-ndjson)

### 1.5 Review Queue
```
GET /api/v1/batches/{batch_id}/review
```

**Response:**
```json
{
  "items": [
    {
      "question_id": "uuid",
      "reason_codes": ["low_confidence", "validation_failed"],
      "question_preview": { /* truncated question */ },
      "validation_errors": [...]
    }
  ],
  "total": 5
}
```

### 1.6 Health & Metrics
```
GET /api/v1/health
GET /api/v1/metrics
```

### 1.7 Testgen Endpoints (Test & Practice Agent)

Deterministic test/practice assembly from the blueprint bank. No LLM calls.
All endpoints below require the `X-API-Key` header except `/api/v1/health`.

**Authentication:** header `X-API-Key: <QME_API_KEY>`. Missing/wrong key →
`401` with error code `UNAUTHORIZED`. The key is read from the server
environment only; requests never carry file paths (the blueprint path is
server configuration, `QME_BLUEPRINT_PATH`).

**Canonical keys**

- *Source key* = `source.name` verbatim (e.g. `Quantitative Aptitude EBook`).
- *Chapter key* = `"<source.name> › <chapter>"` — engine-derived; upstream
  data is never altered. Filters AND together: `sources × chapters × difficulty`.
- Knowledge (formulas / shortcut tricks) is **source-less**: one shared
  aptitude pool keyed by unqualified chapter/topic names.

```
GET  /api/v1/health
GET  /api/v1/bank/meta
POST /api/v1/tests
POST /api/v1/tests/submit
POST /api/v1/practice
GET  /api/v1/chapters/{chapter_key}/knowledge
```

**GET /api/v1/bank/meta** — discovery for callers building requests
(feasibility pickers read `sources[].chapters[].difficulty_counts`).

**Response 200:**
```json
{
  "sources": [
    {
      "name": "Quantitative Aptitude EBook",
      "question_count": 1310,
      "chapters": [
        {
          "key": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
          "label": "Percentage, Profit & Loss",
          "question_count": 123,
          "difficulty_counts": {"easy": 52, "medium": 71, "hard": 0}
        }
      ]
    }
  ],
  "chapters": ["Quantitative Aptitude EBook › Average", "..."],
  "topics": ["Average / Replacement Average", "..."],
  "difficulties": ["easy", "hard", "medium"],
  "question_count": 1310,
  "buckets": {"<chapter>": {"<topic>": {"<difficulty>": 12}}},
  "knowledge_coverage": {"covered_chapters": ["Average"], "missing_chapters": []},
  "contract": { /* blueprint test_generation_contract verbatim */ }
}
```
`chapters` holds qualified keys (sorted); `buckets` stays blueprint verbatim
(unqualified); `knowledge_coverage` reports over unqualified chapter names —
knowledge is optional, never load-blocking.

**POST /api/v1/tests** — exactly one of two body shapes per request.

*Friendly shape (recommended):*
```json
{
  "title": "Unit Test 3",
  "seed": 42,
  "sources": ["Quantitative Aptitude EBook"],
  "chapters": ["Quantitative Aptitude EBook › Percentage, Profit & Loss"],
  "difficulty": {"mode": "mixed", "counts": {"easy": 10, "medium": 5, "hard": 5}},
  "count": 20
}
```
- `seed` optional — generated when absent; same seed + same request ⇒ same test.
- `sources` absent = all sources; `chapters` absent = all chapters.
- `difficulty.mode = "single"` takes `"value": "easy|medium|hard"`;
  `"mixed"` takes non-negative `"counts"` (keys ⊆ easy/medium/hard) whose
  sum equals `count`.

*Legacy shape (kept; additive optional `source` field):*
```json
{
  "selections": [
    {"count": 10, "chapter": "Percentage, Profit & Loss",
     "source": "Quantitative Aptitude EBook", "difficulty": "hard"}
  ]
}
```
Legacy `chapter` is unqualified: it resolves when it matches exactly one
source; ambiguous across sources → 422 `INVALID_INPUT` (never silently
merged). With a single source, legacy behavior is identical to v1. The
legacy shape keeps v1 semantics (per-selection `count ≥ 1`; the friendly
rule table below applies to the friendly shape only).

*Test rules* — every violation → 422 `INVALID_INPUT`, `details` states the
rule, the actual value, and valid/available options:

| Rule | Value |
|---|---|
| `count` multiple of | 5 |
| `count` minimum | 10 (any explicit chapter scope) |
| `count` minimum | 30 when `chapters` is absent (all-chapters test) |
| mixed `counts` sum | must equal `count` |
| feasibility | `sources × chapters × difficulty` must hold ≥ `count` questions; `details.available_by_difficulty` reports what exists (10 chapters have zero hard) |
| both shapes in one body | rejected as ambiguous |
| unknown source/chapter | rejected; `details` lists valid names |

**Response 200:** the `GeneratedTest` model verbatim — `test_id`, `title`,
`generated_at`, `contract_source`, `selections_applied`,
`selection_rules_applied`, `questions`, `answer_key`, `coverage`, `timing`,
`shortages`, `notes`. Questions are byte-for-byte the bank records (never
altered). `Coverage` gains `by_source`; `by_chapter` keys are qualified
chapter keys. Answers/solutions are included in the response (the frontend
decides when to reveal them).

**POST /api/v1/tests/submit** — end the test and deliver results
(stateless round-trip; no server-side session).

```json
{
  "test_id": "T-20261005-...",
  "request": { /* exact POST /api/v1/tests body, including seed */ },
  "answers": {"p5-1": "B", "p9-3": "C"},
  "elapsed_seconds": 540
}
```
`test_id` (optional) is the id echoed by the test response — carried into
the result for traceability. The server regenerates the test
deterministically from `request` and scores `answers` (`question_id` →
option key) against it. Repeated submits with the same request + answers
are idempotent. `elapsed_seconds` is recorded, not enforced — the frontend
owns the timer and auto-submits when it expires; the client stores the
returned result (no GET results endpoint).

**Response 200:** `TestResult`:
```json
{
  "test_id": "T-20261005-...",
  "score": {"correct": 14, "total": 20, "percent": 70.0},
  "by_difficulty": {"easy": {"correct": 8, "total": 10}},
  "by_chapter": {"Quantitative Aptitude EBook › Average": {"correct": 3, "total": 3}},
  "by_source": {"Quantitative Aptitude EBook": {"correct": 14, "total": 20}},
  "elapsed_seconds": 540,
  "results": [
    {"question_id": "p5-1", "your_answer": "B", "correct_answer": "A",
     "is_correct": false, "solution_steps": ["..."], "difficulty": "hard",
     "chapter": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
     "source": "Quantitative Aptitude EBook"}
  ]
}
```

**POST /api/v1/practice** — paginated practice pool; correct answers and
solutions are always included.

```json
{
  "count": 5, "page": 2, "seed": 42,
  "source": "Quantitative Aptitude EBook",
  "chapter": "Quantitative Aptitude EBook › Percentage, Profit & Loss",
  "topic": "...", "difficulty": "hard",
  "mode": "progressive", "include_knowledge": true
}
```
- `count` = page size (default 10, `≥ 1`), `page` = 1-based (default 1),
  `source` absent = all sources. No test rules apply (no minimum/multiple).
- Pagination is deterministic: the pool is ordered once from `seed` and
  sliced — pages are disjoint and cover the pool. The response **echoes
  `seed`**: reuse it with `page + 1` for the next page; changing any filter
  or the seed reshuffles the pool.
- Chapter resolution follows the same unique-match / ambiguity rule as tests.

**Response 200:** the `PracticeSet` model verbatim (`practice_id`, `mode`,
`questions`, `coverage`, `timing`, `shortages`, `topic_knowledge`,
`chapter_formula_summary`) plus `seed` and:
```json
"pagination": {"page": 2, "count": 5, "total": 123, "total_pages": 25, "has_more": true}
```
A partial last page is normal; pool size is reported via
`pagination.total` — practice never reports shortages (shortages remain a
`/tests` concern; the field stays empty).

**GET /api/v1/chapters/{chapter_key}/knowledge?topic=<name>** — formulas &
shortcut tricks on demand (frontend calls it only when the user asks).
- `chapter_key` accepts a qualified key (the source part is ignored for
  lookup) or a raw chapter name; `topic` narrows to one topic.
- **Response 200:**
```json
{
  "chapter": "Percentage, Profit & Loss",
  "topic": null,
  "formula_summary": ["..."],
  "topics": {"Linear Equations": {"formulas": ["..."], "short_tricks": ["..."]}}
}
```
- Chapter exists but has no knowledge → 200 with empty lists (knowledge is
  optional per source); unknown chapter → 404 `NOT_FOUND`.

**Status codes:**

| Condition | Status | error.code |
|---|---|---|
| Missing/wrong `X-API-Key` | 401 | `UNAUTHORIZED` |
| Body fails schema validation | 422 | `VALIDATION_ERROR` |
| Test rule violated / unknown or ambiguous filter / infeasible scope | 422 | `INVALID_INPUT` — `details` states rule, actual value, valid/available options |
| `SelectionError` (practice pool empty) | 422 | `INVALID_INPUT` |
| Submit answers do not match the regenerated test | 422 | `ANSWER_MISMATCH` |
| Unknown chapter on the knowledge endpoint | 404 | `NOT_FOUND` |
| Bank broken/missing (`ContractError`) | 503 | `SERVICE_UNAVAILABLE` — `details.issues` is the contract field report |

`UNAUTHORIZED`, `SERVICE_UNAVAILABLE`, `NOT_FOUND`, and `ANSWER_MISMATCH`
extend the §4 error-code enum. Every error body follows the §4 envelope and
carries a per-request `request_id`. Responses are stateless JSON — the API
never writes files (use the `qme testgen` / `qme practice` CLI commands for
file output).

**Bank adoption (multi-source, future-proofing):** the bank is one merged
`book_questions_agent_ready.jsonl` + blueprint; a new source (e.g. TCS NQT)
appears the moment its records exist — chapters/topics/sources are derived
from the questions, so `/bank/meta` reflects them automatically.
`question_id` must be globally unique across sources (prefix per source,
e.g. `tcs-12`); the loader hard-stops with a field report and never silently
rewrites ids. Knowledge is optional per chapter — missing entries surface via
`knowledge_coverage` and empty knowledge responses — so a new source ships
before its formulas exist; backfilling the knowledge JSON is adopted on the
next request. Replacing any of the three bank files hot-reloads the cache
(no restart required).

## 2. Internal Module Interfaces (Python Protocols)

### 2.1 QuestionClassifier
```python
from typing import Protocol
from pydantic import BaseModel

class ClassificationInput(BaseModel):
    question_text: str
    options: dict[str, str]
    correct_answer: str
    context: dict | None = None

class ClassificationResult(BaseModel):
    category_id: str
    topic_id: str
    subtopic_id: str | None = None
    concepts: list[str]
    question_type: str  # mcq, numeric, multi_select
    tags: list[str] = []
    confidence: float  # 0.0-1.0
    reasoning: str | None = None

class QuestionClassifier(Protocol):
    async def classify(self, input: ClassificationInput) -> ClassificationResult: ...
    def get_taxonomy_version(self) -> int: ...
```

### 2.2 DifficultyEngine
```python
class DifficultyInput(BaseModel):
    question_text: str
    options: dict[str, str]
    correct_answer: str
    classification: ClassificationResult

class DifficultyFactor(BaseModel):
    name: str
    weight: float  # 0.0-1.0
    score: float   # 0.0-10.0
    reasoning: str

class DifficultyResult(BaseModel):
    score: float  # 0.0-10.0
    rating: str   # easy, medium, hard
    factors: list[DifficultyFactor]
    estimated_time_sec: int
    confidence: float
    methodology_version: str

class DifficultyEngine(Protocol):
    async def score(self, input: DifficultyInput) -> DifficultyResult: ...
```

### 2.3 SolutionEngine
```python
class SolutionInput(BaseModel):
    question_text: str
    options: dict[str, str]
    correct_answer: str
    classification: ClassificationResult
    existing_solution: str | None = None  # If source provides one

class SolutionStep(BaseModel):
    step_number: int
    description: str
    formula_refs: list[str] = []
    calculation: str | None = None
    result: str | None = None

class SolutionResult(BaseModel):
    steps: list[SolutionStep]
    formulas_used: list[str]  # Formula names/refs
    calculations: list[dict]  # {expr, result}
    final_answer: str
    source: str  # extracted, generated
    confidence: float
    validation_status: str  # pending, validated, failed

class SolutionEngine(Protocol):
    async def solve(self, input: SolutionInput) -> SolutionResult: ...
    async def extract_existing(self, raw_solution: str) -> SolutionResult: ...
```

### 2.4 FormulaExtractor
```python
class FormulaInput(BaseModel):
    question_text: str
    solution: SolutionResult
    classification: ClassificationResult

class FormulaRef(BaseModel):
    name: str
    expression: str
    category: str
    reference_id: str | None = None  # Link to future Formula KB
    confidence: float

class FormulaResult(BaseModel):
    formulas: list[FormulaRef]
    unknown_formulas: list[str]  # Names not in KB

class FormulaExtractor(Protocol):
    async def extract(self, input: FormulaInput) -> FormulaResult: ...
```

### 2.5 Validator
```python
class ValidationInput(BaseModel):
    enriched_question: EnrichedQuestion  # Full assembled object

class ValidationIssue(BaseModel):
    layer: str  # schema, answer, calculation, formula, solution_answer, metadata, confidence
    severity: str  # error, warning
    code: str
    message: str
    field: str | None = None

class ValidationResult(BaseModel):
    status: str  # validated, needs_review, failed
    issues: list[ValidationIssue]
    overall_confidence: float

class Validator(Protocol):
    async def validate(self, input: ValidationInput) -> ValidationResult: ...
```

## 3. Data Models (Pydantic Schemas)

### 3.1 EnrichedQuestion (Main Output)
```python
class EnrichedQuestion(BaseModel):
    question_id: UUID
    content_hash: str
    question_text: str
    options: dict[str, str]
    correct_answer: str
    category_id: str
    topic_id: str
    subtopic_id: str | None = None
    concepts: list[str]
    question_type: str
    difficulty_score: float
    difficulty_rating: str
    difficulty_factors: dict[str, float]
    estimated_time_sec: int
    solution: SolutionResult
    solution_source: str
    formulas_used: list[FormulaRef]
    source_name: str
    source_type: str
    source_identifier: str
    source_page: int | None = None
    source_question_id: str | None = None
    processing_version: str
    model_used: str
    prompt_version: str
    processing_timestamp: datetime
    processing_duration_ms: int
    token_usage: dict[str, int]
    estimated_cost_usd: float
    validation_status: str
    validation_errors: list[ValidationIssue]
    validation_warnings: list[ValidationIssue]
    status: str
```

### 3.2 Batch Config
```python
class BatchConfig(BaseModel):
    generate_solutions: bool = True
    extract_formulas: bool = True
    validate: bool = True
    checkpoint_interval: int = 10
    max_retries: int = 3
    model_overrides: dict[str, str] = {}  # e.g., {"classifier": "gpt-4o-mini"}
    confidence_thresholds: dict[str, float] = {
        "classification": 0.7,
        "difficulty": 0.7,
        "solution": 0.8,
        "formula": 0.7
    }
```

## 4. Error Responses

```json
{
  "error": {
    "code": "VALIDATION_ERROR|PROCESSING_ERROR|RATE_LIMITED|INVALID_INPUT|UNAUTHORIZED|SERVICE_UNAVAILABLE|NOT_FOUND|ANSWER_MISMATCH",
    "message": "Human-readable description",
    "details": { /* field-specific errors */ },
    "request_id": "uuid"
  }
}
```

## 5. CLI Interface Contracts

### 5.1 Ingest Command
```
qme ingest --input <file> --output <dir> --format <jsonl|csv|pdf|docx|txt>
```

### 5.2 Process Command
```
qme process --input <file> --output <dir> --checkpoint-dir <dir> --config <file>
```

### 5.3 Review Command
```
qme review --input <review.jsonl> --action <approve|reject|edit> --output <file>
```

### 5.4 Eval Command
```
qme eval --gold <gold.jsonl> --pred <pred.jsonl> --output <report.json>
```

## 6. Webhook Contracts (Future)

```
POST /webhooks/batch-complete
POST /webhooks/question-failed
POST /webhooks/review-needed
```
