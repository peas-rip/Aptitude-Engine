"""Shared parser contracts: raw input shape, parse results, helper builder.

Parsers produce :class:`RawRecord` objects; the normalizer turns those into
``NormalizedQuestion``. Required-field validation happens once, here, so all
three parsers report missing-field errors identically.
"""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, ValidationError


class PartialSource(BaseModel):
    """Source fields as supplied by input files; SourceTracker completes them.

    The contract's ``SourceInfo`` requires name/type/identifier, which files
    rarely all provide, so the parse layer records what exists and the
    source tracker (FE-008) fills the rest with logged defaults.
    """

    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    type: str | None = None
    identifier: str | None = None
    page: int | None = None
    question_id: str | None = None


class RawQuestion(BaseModel):
    """Loose input shape accepted from JSONL/CSV/TXT files (FE-001)."""

    model_config = ConfigDict(extra="ignore")

    question_text: str
    options: dict[str, str] = {}
    correct_answer: str
    source: PartialSource | None = None


class RawRecord(BaseModel):
    """One parsed question plus where it came from (line/row/block)."""

    location: str
    question: RawQuestion


class ParseFailure(BaseModel):
    """A record the parser could not accept, with enough context to fix it."""

    location: str
    error: str
    raw: str = ""


class ParseResult(BaseModel):
    """Parser output: accepted records, failures, and non-fatal warnings."""

    records: list[RawRecord] = []
    failures: list[ParseFailure] = []
    warnings: list[str] = []


def make_failure(location: str, error: str, raw: str = "") -> ParseFailure:
    """Build a ParseFailure with a truncated raw snippet."""
    return ParseFailure(location=location, error=error, raw=_snippet(raw))


def build_record(location: str, payload: dict, raw: str) -> RawRecord | ParseFailure:
    """Validate a loose payload into a RawRecord, or report a typed failure.

    Pydantic ValidationError -> ParseFailure so required-field problems
    (missing question_text, missing correct_answer) are never silent.
    """
    try:
        return RawRecord(location=location, question=RawQuestion.model_validate(payload))
    except ValidationError as exc:
        issues = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        return make_failure(location, f"invalid record: {issues}", raw)


@runtime_checkable
class QuestionParser(Protocol):
    """Parser interface: text -> structured records with per-record failures."""

    format_name: str

    def parse(self, text: str) -> ParseResult:
        """Parse full file content. Never raises for per-record problems."""
        ...


def _snippet(raw: str, limit: int = 200) -> str:
    raw = raw.strip()
    return raw if len(raw) <= limit else raw[:limit] + "...[truncated]"
