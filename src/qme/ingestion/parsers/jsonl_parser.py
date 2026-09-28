"""JSONL parser: one JSON object per line (FE-001).

Malformed lines are skipped and recorded as failures with their line number;
a bad line never aborts the file.
"""

import json

from qme.ingestion.parsers.base import ParseResult, RawRecord, build_record, make_failure


class JSONLParser:
    format_name = "jsonl"

    def parse(self, text: str) -> ParseResult:
        result = ParseResult()
        for line_no, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            location = f"line {line_no}"
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                result.failures.append(make_failure(location, f"invalid JSON: {exc.msg}", line))
                continue
            if not isinstance(payload, dict):
                result.failures.append(
                    make_failure(location, "expected a JSON object, got another JSON value", line)
                )
                continue
            record = build_record(location, payload, line)
            if isinstance(record, RawRecord):
                result.records.append(record)
            else:
                result.failures.append(record)
        return result
