"""Ingestor: file -> parse -> source resolution -> normalize (FE-001 flow).

Factory pattern per ``docs/IMPLEMENTATION_ORDER.md`` Step 2: the format
override is validated up front (fail fast), while detection from content
happens inside :meth:`ingest` once the file is read. Per-record problems are
collected as failures (log + skip + continue); file-level problems raise
:class:`IngestionError` with context.
"""

import logging
from pathlib import Path

from pydantic import BaseModel

from qme.core.exceptions import IngestionError, NormalizationError
from qme.core.models import NormalizedQuestion
from qme.ingestion.normalizer import Normalizer
from qme.ingestion.parsers import detect_format, get_parser
from qme.ingestion.parsers.base import ParseResult, QuestionParser
from qme.ingestion.source_tracker import SourceTracker

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 10 * 1024 * 1024  # FE-001 security limit


class IngestFailure(BaseModel):
    """A record rejected at parse or normalize time, with stage context."""

    location: str
    stage: str  # parse | normalize
    error: str
    raw: str = ""


class IngestResult(BaseModel):
    """Outcome of one ingest run: successes plus explicit failure records."""

    input_path: str
    format: str
    questions: list[NormalizedQuestion]
    failures: list[IngestFailure]

    @property
    def total(self) -> int:
        return len(self.questions) + len(self.failures)

    @property
    def failed(self) -> int:
        return len(self.failures)


class Ingestor:
    """Reads one input file and produces normalized questions."""

    def __init__(
        self,
        *,
        format_override: str | None = None,
        normalizer: Normalizer | None = None,
        source_tracker: SourceTracker | None = None,
    ) -> None:
        if format_override is not None:
            get_parser(format_override)  # raises for unknown or deferred formats
        self._format_override = format_override
        self._normalizer = normalizer or Normalizer()
        self._source_tracker = source_tracker or SourceTracker()

    @classmethod
    def create(cls, fmt: str | None = None) -> "Ingestor":
        """Factory: validate an explicit format now; detect content later."""
        normalized = fmt.strip().lower() if fmt else None
        return cls(format_override=normalized)

    def ingest(self, input_path: Path) -> IngestResult:
        """Run the full ingestion pipeline for one file."""
        self._check_file(input_path)
        text = self._read(input_path)
        parser = self._resolve_parser(input_path, text)
        parsed = parser.parse(text)
        questions, failures = self._normalize(parsed, input_path, parser.format_name)
        for warning in parsed.warnings:
            logger.warning("ingestion warning | %s | %s", input_path.name, warning)
        for failure in failures:
            logger.warning(
                "record rejected | %s | location=%s | stage=%s | error=%s",
                input_path.name,
                failure.location,
                failure.stage,
                failure.error,
            )
        logger.info(
            "ingested %s | format=%s | ok=%d | failed=%d",
            input_path.name,
            parser.format_name,
            len(questions),
            len(failures),
        )
        return IngestResult(
            input_path=str(input_path),
            format=parser.format_name,
            questions=questions,
            failures=failures,
        )

    @staticmethod
    def _check_file(path: Path) -> None:
        if not path.exists():
            raise IngestionError("input file not found", context={"path": str(path)})
        if not path.is_file():
            raise IngestionError("input path is not a file", context={"path": str(path)})
        size = path.stat().st_size
        if size > _MAX_FILE_BYTES:
            raise IngestionError(
                f"input file is {size} bytes; limit is {_MAX_FILE_BYTES} bytes",
                context={"path": str(path)},
            )

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise IngestionError(
                f"input file is not valid UTF-8: {exc.reason}",
                context={"path": str(path), "byte_offset": exc.start},
            ) from exc

    def _resolve_parser(self, path: Path, text: str) -> QuestionParser:
        if self._format_override is not None:
            return get_parser(self._format_override)
        return get_parser(detect_format(path, text))

    def _normalize(
        self, parsed: ParseResult, input_path: Path, fallback_type: str
    ) -> tuple[list[NormalizedQuestion], list[IngestFailure]]:
        questions: list[NormalizedQuestion] = []
        failures: list[IngestFailure] = [
            IngestFailure(location=f.location, stage="parse", error=f.error, raw=f.raw)
            for f in parsed.failures
        ]
        for record in parsed.records:
            source = self._source_tracker.resolve(
                record.question.source,
                input_path=input_path,
                fallback_type=fallback_type,
            )
            try:
                questions.append(self._normalizer.normalize(record, source))
            except NormalizationError as exc:
                failures.append(
                    IngestFailure(
                        location=record.location,
                        stage="normalize",
                        error=exc.message,
                        raw=record.question.model_dump_json(),
                    )
                )
        return questions, failures


def ingest_file(input_path: Path, fmt: str | None = None) -> IngestResult:
    """One-call convenience: validate format (if given) and ingest."""
    return Ingestor.create(fmt).ingest(input_path)
