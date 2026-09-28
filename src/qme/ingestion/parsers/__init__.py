"""Format detection and parser registry (FE-001).

Extension is authoritative when known; unknown extensions fall back to a
content sniff (JSONL line -> CSV shape -> TXT labels). Anything unresolved
fails with an explicit instruction to pass ``--format``.
"""

import json
import re
from pathlib import Path

from qme.core.exceptions import IngestionError
from qme.ingestion.parsers.base import QuestionParser
from qme.ingestion.parsers.csv_parser import CSVParser
from qme.ingestion.parsers.jsonl_parser import JSONLParser
from qme.ingestion.parsers.txt_parser import TXTParser

SUPPORTED_FORMATS: frozenset[str] = frozenset({"jsonl", "csv", "txt"})
DEFERRED_FORMATS: frozenset[str] = frozenset({"pdf", "docx"})

_EXTENSIONS = {".jsonl": "jsonl", ".ndjson": "jsonl", ".csv": "csv", ".txt": "txt", ".text": "txt"}
_DEFERRED_EXTENSIONS = {".pdf": "pdf", ".docx": "docx"}

_PARSERS: dict[str, QuestionParser] = {
    "jsonl": JSONLParser(),
    "csv": CSVParser(),
    "txt": TXTParser(),
}


def get_parser(fmt: str) -> QuestionParser:
    """Return the parser for a validated format name."""
    if fmt in DEFERRED_FORMATS:
        raise IngestionError(
            f"{fmt.upper()} input is not supported yet (scheduled for Step 9: document parsers)",
            context={"format": fmt},
        )
    if fmt not in _PARSERS:
        raise IngestionError(
            f"unknown format {fmt!r}; supported formats: {', '.join(sorted(SUPPORTED_FORMATS))}",
            context={"format": fmt},
        )
    return _PARSERS[fmt]


def detect_format(path: Path, text: str) -> str:
    """Resolve the input format from extension, or sniff content as fallback."""
    ext = path.suffix.lower()
    if ext in _DEFERRED_EXTENSIONS:
        get_parser(_DEFERRED_EXTENSIONS[ext])  # always raises: deferred format
    if ext in _EXTENSIONS:
        return _EXTENSIONS[ext]
    sniffed = _sniff(text)
    if sniffed:
        return sniffed
    raise IngestionError(
        f"cannot detect format of {path.name!r} (extension {ext or '<none>'}); "
        f"pass --format with one of: {', '.join(sorted(SUPPORTED_FORMATS))}",
        context={"path": str(path)},
    )


def _sniff(text: str) -> str | None:
    """Best-effort content detection for files with unknown extensions."""
    for line in text.splitlines():
        if line.strip():
            first = line.strip()
            try:
                if isinstance(json.loads(first), dict):
                    return "jsonl"
            except json.JSONDecodeError:
                pass
            break
    if _looks_like_csv(text):
        return "csv"
    if _looks_like_txt(text):
        return "txt"
    return None


def _looks_like_csv(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()][:5]
    if len(lines) < 2:
        return False
    widths = {line.count(",") for line in lines}
    return len(widths) == 1 and next(iter(widths)) >= 1


def _looks_like_txt(text: str) -> bool:
    return bool(re.search(r"^(?:Q|Question)\s*:", text, re.IGNORECASE | re.MULTILINE)) and bool(
        re.search(r"^(?:Answer|Ans)\s*:", text, re.IGNORECASE | re.MULTILINE)
    )
