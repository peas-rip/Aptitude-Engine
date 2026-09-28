"""CSV parser with or without a header row (FE-001 edge cases).

Canonical columns (headerless files use this order):

    question_text, option_a..option_f, correct_answer,
    source_name, source_type, source_identifier, source_page, source_question_id

Accepted header aliases (case-insensitive): ``question`` -> question_text,
``answer`` -> correct_answer, ``options`` -> JSON dict of options, ``page`` ->
source_page, ``question_id`` -> source_question_id. Unknown columns are
reported as warnings, never silently dropped without a trace.
"""

import csv
import io
import json

from qme.ingestion.parsers.base import ParseResult, RawRecord, build_record, make_failure

_CANONICAL_HEADERLESS = [
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_answer",
    "source_name",
    "source_type",
    "source_identifier",
    "source_page",
    "source_question_id",
]

_HEADER_ALIASES = {
    "question": "question_text",
    "answer": "correct_answer",
    "options": "options",
    "page": "source_page",
    "question_id": "source_question_id",
    "sourceid": "source_identifier",
}

_OPTION_COLUMNS = {f"option_{c}": c.upper() for c in "abcdef"}

_SOURCE_COLUMNS = {
    "source_name": "name",
    "source_type": "type",
    "source_identifier": "identifier",
    "source_page": "page",
    "source_question_id": "question_id",
}


class CSVParser:
    format_name = "csv"

    def parse(self, text: str) -> ParseResult:
        result = ParseResult()
        rows = [row for row in csv.reader(io.StringIO(text)) if any(cell.strip() for cell in row)]
        if not rows:
            result.warnings.append("empty CSV file")
            return result

        header = self._detect_header(rows[0])
        if header is not None:
            columns = [_HEADER_ALIASES.get(c.strip().lower(), c.strip().lower()) for c in rows[0]]
            unknown = [c for c in columns if not self._is_known_column(c)]
            if unknown:
                result.warnings.append(f"ignored unknown columns: {', '.join(unknown)}")
            data_rows = rows[1:]
        else:
            columns = list(_CANONICAL_HEADERLESS)
            data_rows = rows
            if len(rows[0]) > len(columns):
                result.warnings.append("headerless CSV: extra trailing columns ignored")

        for row_no, row in enumerate(data_rows, start=2 if header is not None else 1):
            location = f"row {row_no}"
            if len(row) > len(columns):
                result.failures.append(
                    make_failure(
                        location,
                        f"expected at most {len(columns)} columns, got {len(row)}",
                        ",".join(row),
                    )
                )
                continue
            # Short rows are padded by dict defaults; strict=False is intentional.
            payload = self._row_to_payload(dict(zip(columns, row, strict=False)), location, result)
            record = build_record(location, payload, ",".join(row))
            if isinstance(record, RawRecord):
                result.records.append(record)
            else:
                result.failures.append(record)
        return result

    @staticmethod
    def _detect_header(first_row: list[str]) -> list[str] | None:
        known = set(_CANONICAL_HEADERLESS) | set(_HEADER_ALIASES) | set(_OPTION_COLUMNS)
        lowered = {cell.strip().lower() for cell in first_row}
        return first_row if lowered & known else None

    @staticmethod
    def _is_known_column(column: str) -> bool:
        return (
            column in _CANONICAL_HEADERLESS
            or column in _HEADER_ALIASES.values()
            or column in _OPTION_COLUMNS
            or column in _SOURCE_COLUMNS
        )

    @staticmethod
    def _row_to_payload(cells: dict[str, str], location: str, result: ParseResult) -> dict:
        payload: dict = {}
        for key in ("question_text", "correct_answer"):
            if (value := cells.get(key, "").strip()):
                payload[key] = value

        options: dict[str, str] = {}
        if (raw_options := cells.get("options", "").strip()):
            try:
                parsed = json.loads(raw_options)
                if isinstance(parsed, dict):
                    options.update({str(k): str(v) for k, v in parsed.items()})
                else:
                    result.warnings.append(f"{location}: options column is not a JSON object, ignored")
            except json.JSONDecodeError:
                result.warnings.append(f"{location}: options column is not valid JSON, ignored")
        for column, key in _OPTION_COLUMNS.items():
            if column in cells and cells[column].strip():
                options[key] = cells[column].strip()
        if options:
            payload["options"] = options

        source: dict = {}
        for column, field in _SOURCE_COLUMNS.items():
            if column not in cells:
                continue
            value = cells[column].strip()
            if not value:
                continue
            if field == "page":
                try:
                    source["page"] = int(value)
                except ValueError:
                    result.warnings.append(f"{location}: source_page {value!r} is not an integer, ignored")
            else:
                source[field] = value
        if source:
            payload["source"] = source
        return payload
