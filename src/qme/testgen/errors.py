"""Test & Practice Agent error types.

Every failure is a :class:`QMEError` subclass so callers share one handling
path with the rest of the engine; the agent adds two precise categories:

- :class:`ContractError` — an upstream file violates the blueprint contract
  (hard stop with a field-level report; never silently repaired).
- :class:`SelectionError` — a request cannot be satisfied against the bank
  (unknown filter values, no matching questions).
"""

from qme.core.exceptions import QMEError


class TestGenError(QMEError):
    """Base error for the Test & Practice Agent."""


class ContractError(TestGenError):
    """Upstream bank/blueprint/knowledge files violate the expected contract."""

    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        self.issues = issues or []
        if self.issues:
            detail = "\n  - ".join(self.issues)
            message = f"{message}\n  - {detail}"
        super().__init__(message)


class SelectionError(TestGenError):
    """A test/practice request cannot be satisfied against the bank.

    ``details`` is machine-readable context for the API error envelope
    (API_CONTRACTS 1.7): available filter values or the failed filters.
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


class SubmissionError(TestGenError):
    """A submission's answers do not map onto the regenerated test.

    Surfaced as ``422 ANSWER_MISMATCH`` (API_CONTRACTS 1.7); ``details``
    names the offending question ids / option keys.
    """

    def __init__(self, message: str, details: dict | None = None) -> None:
        self.details = details or {}
        super().__init__(message)
