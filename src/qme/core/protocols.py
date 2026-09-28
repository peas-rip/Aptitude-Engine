"""Protocol interfaces for pipeline stages.

Every stage implements its Protocol (hard rule in AGENTS.md) so modules stay
unit-testable with mocks and swappable for smaller/faster models later.
"""

from typing import Protocol, runtime_checkable

from qme.core.models import (
    ClassificationInput,
    ClassificationResult,
    DifficultyInput,
    DifficultyResult,
    EnrichedQuestion,
    FormulaInput,
    FormulaResult,
    SolutionInput,
    SolutionResult,
    ValidationInput,
    ValidationResult,
)


@runtime_checkable
class QuestionClassifier(Protocol):
    """Assigns hierarchical taxonomy labels to a question (FE-002)."""

    async def classify(self, input: ClassificationInput) -> ClassificationResult: ...

    def get_taxonomy_version(self) -> int: ...


@runtime_checkable
class DifficultyEngine(Protocol):
    """Produces a structured 0-10 difficulty score with factors (FE-003)."""

    async def score(self, input: DifficultyInput) -> DifficultyResult: ...


@runtime_checkable
class SolutionEngine(Protocol):
    """Extracts or generates a step-by-step solution (FE-004)."""

    async def solve(self, input: SolutionInput) -> SolutionResult: ...

    async def extract_existing(self, raw_solution: str) -> SolutionResult: ...


@runtime_checkable
class FormulaExtractor(Protocol):
    """Identifies formulas used, returning KB-ready references (FE-005)."""

    async def extract(self, input: FormulaInput) -> FormulaResult: ...


@runtime_checkable
class Validator(Protocol):
    """Runs the 7-layer validation pipeline (FE-006)."""

    async def validate(self, input: ValidationInput) -> ValidationResult: ...


__all__ = [
    "QuestionClassifier",
    "DifficultyEngine",
    "SolutionEngine",
    "FormulaExtractor",
    "Validator",
    "ClassificationInput",
    "ClassificationResult",
    "DifficultyInput",
    "DifficultyResult",
    "SolutionInput",
    "SolutionResult",
    "FormulaInput",
    "FormulaResult",
    "ValidationInput",
    "ValidationResult",
    "EnrichedQuestion",
]
