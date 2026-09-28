"""JSONL file writer: one Pydantic model per line (V1 output format).

Shared by ingestion output now and pipeline batch output later
(``docs/IMPLEMENTATION_ORDER.md`` Step 8) so serialization never diverges.
"""

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel


def write_jsonl(path: Path, items: Iterable[BaseModel]) -> int:
    """Overwrite ``path`` with one JSON object per line; return count written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in items:
            handle.write(item.model_dump_json() + "\n")
            count += 1
    return count
