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
    """A test/practice request cannot be satisfied against the bank."""
