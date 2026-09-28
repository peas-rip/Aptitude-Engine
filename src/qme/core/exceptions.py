"""Custom exceptions.

Every error carries context; nothing fails silently (hard rule in AGENTS.md).
"""

from typing import Any


class QMEError(Exception):
    """Base error for the Question Metadata Engine."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} | context={self.context}"
        return self.message


class IngestionError(QMEError):
    """Input file could not be read or parsed."""


class NormalizationError(QMEError):
    """Raw question failed normalization rules."""


class LLMError(QMEError):
    """LLM gateway failure (API, timeout, or response handling)."""


class LLMRateLimitError(LLMError):
    """Provider rate limit hit; caller should back off and retry."""


class LLMResponseFormatError(LLMError):
    """Model output did not conform to the required structured schema."""


class PipelineError(QMEError):
    """A pipeline stage failed after exhausting retries."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        question_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = dict(context or {})
        if stage is not None:
            ctx["stage"] = stage
        if question_id is not None:
            ctx["question_id"] = question_id
        super().__init__(message, context=ctx)
        self.stage = stage
        self.question_id = question_id


class ValidationError(QMEError):
    """Validation pipeline rejected the question (explicit, never silent)."""


class CheckpointError(QMEError):
    """Checkpoint file missing, corrupt, or unwritable."""
