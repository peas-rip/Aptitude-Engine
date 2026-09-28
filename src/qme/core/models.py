"""Canonical Pydantic models — the single source of truth for the pipeline.

Field names and shapes follow ``docs/API_CONTRACTS.md`` sections 2 and 3
exactly. JSONL output, the REST API, and (later) PostgreSQL all derive from
these models — never duplicate a field definition elsewhere.
"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Provenance & ingestion (FE-001, FE-008)
# ---------------------------------------------------------------------------


class SourceInfo(BaseModel):
    """Provenance of a raw question, captured at ingestion."""

    name: str = Field(description="Source title, e.g. book or file name")
    type: str = Field(description="pdf | docx | txt | csv | jsonl | manual | api")
    identifier: str = Field(description="ISBN, DOI, URL, or filename")
    page: int | None = Field(default=None, ge=1)
    question_id: str | None = Field(default=None, description="Original ID in source")


class NormalizedQuestion(BaseModel):
    """Cleaned, structured question ready for the AI pipeline (FE-001 output)."""

    question_text: str = Field(min_length=1)
    options: dict[str, str] = Field(default_factory=dict)
    correct_answer: str = Field(min_length=1)
    source: SourceInfo


# ---------------------------------------------------------------------------
# Classification (API_CONTRACTS 2.1)
# ---------------------------------------------------------------------------


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
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str | None = None


# ---------------------------------------------------------------------------
# Difficulty (API_CONTRACTS 2.2)
# ---------------------------------------------------------------------------


class DifficultyInput(BaseModel):
    question_text: str
    options: dict[str, str]
    correct_answer: str
    classification: ClassificationResult


class DifficultyFactor(BaseModel):
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=10.0)
    reasoning: str


class DifficultyResult(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    rating: str  # easy, medium, hard
    factors: list[DifficultyFactor]
    estimated_time_sec: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)
    methodology_version: str


# ---------------------------------------------------------------------------
# Solution (API_CONTRACTS 2.3)
# ---------------------------------------------------------------------------


class SolutionInput(BaseModel):
    question_text: str
    options: dict[str, str]
    correct_answer: str
    classification: ClassificationResult
    existing_solution: str | None = None


class SolutionStep(BaseModel):
    step_number: int = Field(ge=1)
    description: str = Field(min_length=1)
    formula_refs: list[str] = Field(default_factory=list)
    calculation: str | None = None
    result: str | None = None


class SolutionResult(BaseModel):
    steps: list[SolutionStep]
    formulas_used: list[str]  # Formula names/refs
    calculations: list[dict]  # {expr, result}
    final_answer: str = Field(min_length=1)
    source: str  # extracted, generated
    confidence: float = Field(ge=0.0, le=1.0)
    validation_status: str  # pending, validated, failed


# ---------------------------------------------------------------------------
# Formulas (API_CONTRACTS 2.4)
# ---------------------------------------------------------------------------


class FormulaInput(BaseModel):
    question_text: str
    solution: SolutionResult
    classification: ClassificationResult


class FormulaRef(BaseModel):
    name: str
    expression: str
    category: str
    reference_id: str | None = None  # Link to future Formula KB
    confidence: float = Field(ge=0.0, le=1.0)


class FormulaResult(BaseModel):
    formulas: list[FormulaRef]
    unknown_formulas: list[str]  # Names not in KB


# ---------------------------------------------------------------------------
# Validation (API_CONTRACTS 2.5)
# ---------------------------------------------------------------------------


class ValidationIssue(BaseModel):
    layer: str  # schema, answer, calculation, formula, solution_answer, metadata, confidence
    severity: str  # error, warning
    code: str
    message: str
    field: str | None = None


class ValidationResult(BaseModel):
    status: str  # validated, needs_review, failed
    issues: list[ValidationIssue]
    overall_confidence: float = Field(ge=0.0, le=1.0)


class ValidationInput(BaseModel):
    enriched_question: "EnrichedQuestion"


# ---------------------------------------------------------------------------
# Main output (API_CONTRACTS 3.1)
# ---------------------------------------------------------------------------


class EnrichedQuestion(BaseModel):
    """Fully processed question — the system's primary output."""

    question_id: UUID = Field(default_factory=uuid4)
    content_hash: str = Field(min_length=1, description="SHA256 of normalized content")
    question_text: str = Field(min_length=1)
    options: dict[str, str]
    correct_answer: str = Field(min_length=1)
    category_id: str
    topic_id: str
    subtopic_id: str | None = None
    concepts: list[str]
    question_type: str
    difficulty_score: float = Field(ge=0.0, le=10.0)
    difficulty_rating: str
    difficulty_factors: dict[str, float]
    estimated_time_sec: int = Field(ge=0)
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
    processing_duration_ms: int = Field(ge=0)
    token_usage: dict[str, int]
    estimated_cost_usd: float = Field(ge=0.0)
    validation_status: str
    validation_errors: list[ValidationIssue] = Field(default_factory=list)
    validation_warnings: list[ValidationIssue] = Field(default_factory=list)
    status: str


# ---------------------------------------------------------------------------
# Batch config (API_CONTRACTS 3.2)
# ---------------------------------------------------------------------------


class BatchConfig(BaseModel):
    generate_solutions: bool = True
    extract_formulas: bool = True
    # Name required by API_CONTRACTS 3.2; shadows BaseModel.validate (unused in v2).
    validate: bool = True  # type: ignore[assignment]
    checkpoint_interval: int = Field(default=10, ge=1)
    max_retries: int = Field(default=3, ge=0)
    model_overrides: dict[str, str] = Field(default_factory=dict)
    confidence_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "classification": 0.7,
            "difficulty": 0.7,
            "solution": 0.8,
            "formula": 0.7,
        }
    )


# ---------------------------------------------------------------------------
# REST API envelopes (API_CONTRACTS 1.1 and 4)
# ---------------------------------------------------------------------------


class ProcessQuestionRequest(BaseModel):
    """Body for POST /api/v1/questions/process.

    Note: the example in API_CONTRACTS 1.1 repeats an ``options`` key for
    processing flags; it is modeled here as ``config`` (BatchConfig).
    """

    question_text: str = Field(min_length=1)
    options: dict[str, str] = Field(default_factory=dict)
    correct_answer: str = Field(min_length=1)
    source: SourceInfo
    config: BatchConfig | None = None


class TokenUsage(BaseModel):
    prompt: int = Field(ge=0)
    completion: int = Field(ge=0)
    total: int = Field(ge=0)


class ProcessQuestionResponse(BaseModel):
    question_id: UUID
    status: str
    result: EnrichedQuestion
    processing_time_ms: int = Field(ge=0)
    token_usage: TokenUsage
    estimated_cost_usd: float = Field(ge=0.0)


class ErrorDetail(BaseModel):
    code: str  # VALIDATION_ERROR | PROCESSING_ERROR | RATE_LIMITED | INVALID_INPUT
    message: str
    details: dict | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
