"""Enums and constants shared across the pipeline.

Model fields stay plain ``str`` per ``docs/API_CONTRACTS.md``; these StrEnums
compare equal to their string values, so validation logic can use either form.
"""

from enum import StrEnum


class QuestionType(StrEnum):
    """Classification of answer format."""

    MCQ = "mcq"
    NUMERIC = "numeric"
    MULTI_SELECT = "multi_select"


class DifficultyRating(StrEnum):
    """Bucketed difficulty label (score thresholds live in config)."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SolutionSource(StrEnum):
    """Where the solution came from."""

    EXTRACTED = "extracted"
    GENERATED = "generated"


class SolutionValidationStatus(StrEnum):
    """Validation state of a single solution."""

    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"


class QuestionStatus(StrEnum):
    """Lifecycle status of a processed question.

    Values: processed, validated, needs_review, failed (FE-009).
    """

    PROCESSED = "processed"
    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    """Outcome of the validation pipeline (subset of QuestionStatus)."""

    VALIDATED = "validated"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class SourceType(StrEnum):
    """Origin format of the raw question."""

    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    CSV = "csv"
    JSONL = "jsonl"
    MANUAL = "manual"
    API = "api"


class ValidationLayer(StrEnum):
    """The seven validation layers (FE-006)."""

    SCHEMA = "schema"
    ANSWER = "answer"
    CALCULATION = "calculation"
    FORMULA = "formula"
    SOLUTION_ANSWER = "solution_answer"
    METADATA = "metadata"
    CONFIDENCE = "confidence"


class Severity(StrEnum):
    """Validation issue severity."""

    ERROR = "error"
    WARNING = "warning"


class PipelineStage(StrEnum):
    """Stages of the processing pipeline; used for logs and event records."""

    EXTRACT = "extract"
    CLASSIFY = "classify"
    DIFFICULTY = "difficulty"
    SOLUTION = "solution"
    FORMULA = "formula"
    VALIDATE = "validate"
    OUTPUT = "output"


class ReviewAction(StrEnum):
    """CLI review resolution actions (FE-009)."""

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


# Default confidence thresholds per stage (overridable via BatchConfig).
DEFAULT_CONFIDENCE_THRESHOLDS: dict[str, float] = {
    "classification": 0.7,
    "difficulty": 0.7,
    "solution": 0.8,
    "formula": 0.7,
}

# Valid values for API_CONTRACTS string-typed fields (for docs/tests).
VALID_QUESTION_TYPES: frozenset[str] = frozenset(QuestionType)
VALID_DIFFICULTY_RATINGS: frozenset[str] = frozenset(DifficultyRating)
VALID_QUESTION_STATUSES: frozenset[str] = frozenset(QuestionStatus)
