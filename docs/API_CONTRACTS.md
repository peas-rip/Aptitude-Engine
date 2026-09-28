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
    "code": "VALIDATION_ERROR|PROCESSING_ERROR|RATE_LIMITED|INVALID_INPUT",
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
