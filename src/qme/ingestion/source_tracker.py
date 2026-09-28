"""Source tracker: complete and sanitize provenance at ingestion (FE-008).

Files rarely carry every ``SourceInfo`` field, so missing fields are filled
from the input file context with an explicit log warning — never silently.
"""

import logging
import re
from pathlib import Path

from qme.core.models import SourceInfo
from qme.ingestion.parsers.base import PartialSource

logger = logging.getLogger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_FIELD_LEN = 200


class SourceTracker:
    """Resolve partial/no source metadata into a complete SourceInfo."""

    def resolve(
        self,
        partial: PartialSource | None,
        *,
        input_path: Path,
        fallback_type: str,
    ) -> SourceInfo:
        """Build a SourceInfo, filling gaps from the input file with warnings.

        ``fallback_type`` is the detected input format (jsonl|csv|txt); used
        when the record supplies no source type. For file ingestion the file
        name becomes the source name and identifier (API-driven manual input
        will use type=manual instead, handled outside this file path flow).
        """
        name = _sanitize(partial.name) if partial and partial.name else ""
        source_type = _sanitize(partial.type) if partial and partial.type else ""
        identifier = _sanitize(partial.identifier) if partial and partial.identifier else ""

        missing: list[str] = []
        if not name:
            name = input_path.name
            missing.append("name")
        if not source_type:
            source_type = fallback_type
            missing.append("type")
        if not identifier:
            identifier = input_path.name
            missing.append("identifier")

        if missing:
            logger.warning(
                "Missing source fields %s defaulted from input file; provenance kept explicit",
                missing,
                extra={"input_path": str(input_path), "filled": missing},
            )

        return SourceInfo(
            name=name,
            type=source_type,
            identifier=identifier,
            page=partial.page if partial else None,
            question_id=_sanitize(partial.question_id) if partial and partial.question_id else None,
        )


def _sanitize(value: str) -> str:
    """Strip control characters and cap length (FE-008: identifiers sanitized)."""
    cleaned = _CONTROL_CHARS.sub("", value).strip()
    return cleaned[:_MAX_FIELD_LEN]
