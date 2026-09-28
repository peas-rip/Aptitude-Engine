"""TXT parser: labeled, blank-line-separated question blocks.

Block format::

    Q: What is 20% of 150?
    A) 25
    B) 30
    C) 35
    D) 40
    Answer: B
    Source: R.S. Aggarwal
    Page: 55
    ID: Q101

Labels (case-insensitive): ``Q:``/``Question:`` (question text; following
unlabeled lines continue it), ``A)``/``A.``/``A:`` option lines, ``Answer:``/
``Ans:``, ``Source:``, ``Page:``, ``ID:``. Blocks without a question or
answer become failures; numeric-entry questions simply omit options.
"""

import re

from qme.ingestion.parsers.base import ParseResult, RawRecord, build_record

_QUESTION_RE = re.compile(r"^(?:Q|Question)\s*:\s*(.*)$", re.IGNORECASE)
_OPTION_RE = re.compile(r"^([A-Ha-h])\s*[).:]\s*(.+)$")
_ANSWER_RE = re.compile(r"^(?:Answer|Ans)\s*:\s*(.*)$", re.IGNORECASE)
_SOURCE_RE = re.compile(r"^Source\s*:\s*(.*)$", re.IGNORECASE)
_PAGE_RE = re.compile(r"^Page\s*:\s*(.*)$", re.IGNORECASE)
_ID_RE = re.compile(r"^ID\s*:\s*(.*)$", re.IGNORECASE)


class TXTParser:
    format_name = "txt"

    def parse(self, text: str) -> ParseResult:
        result = ParseResult()
        for block_no, block in enumerate(self._blocks(text), start=1):
            self._parse_block(block_no, block, result)
        if not result.records and not result.failures:
            result.warnings.append("no question blocks found (blocks are separated by blank lines)")
        return result

    @staticmethod
    def _blocks(text: str) -> list[list[str]]:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in text.splitlines():
            if not line.strip():
                if current:
                    blocks.append(current)
                    current = []
                continue
            current.append(line.rstrip())
        if current:
            blocks.append(current)
        return blocks

    def _parse_block(self, block_no: int, lines: list[str], result: ParseResult) -> None:
        location = f"block {block_no}"
        question_parts: list[str] = []
        options: dict[str, str] = {}
        answer: str | None = None
        source_name: str | None = None
        page: str | None = None
        question_id: str | None = None
        seen_answer = False

        for line in lines:
            if match := _QUESTION_RE.match(line):
                question_parts.append(match.group(1).strip())
                continue
            if match := _OPTION_RE.match(line):
                options[match.group(1).upper()] = match.group(2).strip()
                continue
            if match := _ANSWER_RE.match(line):
                answer = match.group(1).strip()
                seen_answer = True
                continue
            if match := _SOURCE_RE.match(line):
                source_name = match.group(1).strip()
                continue
            if match := _PAGE_RE.match(line):
                page = match.group(1).strip()
                continue
            if match := _ID_RE.match(line):
                question_id = match.group(1).strip()
                continue
            if seen_answer or options:
                result.warnings.append(f"{location}: unrecognized line skipped: {line.strip()!r}")
            else:
                question_parts.append(line.strip())

        payload: dict = {"question_text": " ".join(p for p in question_parts if p)}
        if options:
            payload["options"] = options
        if answer is not None:
            payload["correct_answer"] = answer
        if source_name or page or question_id:
            source: dict = {}
            if source_name:
                source["name"] = source_name
            if page:
                try:
                    source["page"] = int(page)
                except ValueError:
                    result.warnings.append(f"{location}: Page {page!r} is not an integer, ignored")
            if question_id:
                source["question_id"] = question_id
            payload["source"] = source

        record = build_record(location, payload, " | ".join(lines))
        if isinstance(record, RawRecord):
            result.records.append(record)
        else:
            result.failures.append(record)
