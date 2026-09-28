"""Unit tests: JSONL/CSV/TXT parsers and format detection (FE-001 Step 2)."""

import json
from pathlib import Path

import pytest

from qme.core.exceptions import IngestionError
from qme.ingestion.parsers import detect_format, get_parser
from qme.ingestion.parsers.base import RawRecord
from qme.ingestion.parsers.csv_parser import CSVParser
from qme.ingestion.parsers.jsonl_parser import JSONLParser
from qme.ingestion.parsers.txt_parser import TXTParser


def _line(payload: dict) -> str:
    return json.dumps(payload)


class TestJSONLParser:
    def test_valid_line_produces_record(self) -> None:
        text = _line({"question_text": "Q1?", "options": {"A": "x"}, "correct_answer": "A"})
        result = JSONLParser().parse(text)
        assert len(result.records) == 1
        assert not result.failures
        assert isinstance(result.records[0], RawRecord)
        assert result.records[0].location == "line 1"

    def test_malformed_line_skipped_with_line_number(self) -> None:
        good = _line({"question_text": "Q2?", "correct_answer": "42"})
        text = "{not valid json}\n" + good
        result = JSONLParser().parse(text)
        assert len(result.records) == 1
        assert len(result.failures) == 1
        assert result.failures[0].location == "line 1"
        assert "invalid JSON" in result.failures[0].error

    def test_blank_lines_skipped_without_counting_as_failures(self) -> None:
        text = "\n\n" + _line({"question_text": "Q3?", "correct_answer": "7"}) + "\n\n"
        result = JSONLParser().parse(text)
        assert len(result.records) == 1
        assert not result.failures

    def test_missing_correct_answer_is_failure(self) -> None:
        result = JSONLParser().parse(_line({"question_text": "Q4?"}))
        assert not result.records
        assert "correct_answer" in result.failures[0].error

    def test_non_object_line_is_failure(self) -> None:
        result = JSONLParser().parse('"just a string"')
        assert not result.records
        assert "JSON object" in result.failures[0].error

    def test_question_without_options_allowed(self) -> None:
        record = JSONLParser().parse(_line({"question_text": "2+2=?", "correct_answer": "4"}))
        assert len(record.records) == 1
        assert record.records[0].question.options == {}

    def test_partial_source_preserved(self) -> None:
        text = _line({"question_text": "Q?", "correct_answer": "A", "source": {"name": "Book"}})
        result = JSONLParser().parse(text)
        assert result.records[0].question.source is not None
        assert result.records[0].question.source.name == "Book"
        assert result.records[0].question.source.type is None


class TestCSVParser:
    def test_header_row_parses_all_columns(self) -> None:
        text = (
            "question_text,option_a,option_b,correct_answer,source_name,source_page\n"
            '"What is 2+2?",3,4,A,Maths Book,12\n'
        )
        result = CSVParser().parse(text)
        assert len(result.records) == 1
        assert not result.failures
        record = result.records[0].question
        assert record.question_text == "What is 2+2?"
        assert record.options == {"A": "3", "B": "4"}
        assert record.source is not None
        assert record.source.name == "Maths Book"
        assert record.source.page == 12

    def test_headerless_uses_canonical_order(self) -> None:
        text = '"Find x",1,2,3,4,B\n'
        result = CSVParser().parse(text)
        assert len(result.records) == 1
        record = result.records[0].question
        assert record.question_text == "Find x"
        assert record.correct_answer == "B"

    def test_header_aliases_question_and_answer(self) -> None:
        text = 'question,answer\n"Is 2 even?",yes\n'
        result = CSVParser().parse(text)
        assert len(result.records) == 1
        assert result.records[0].question.question_text == "Is 2 even?"
        assert result.records[0].question.correct_answer == "yes"

    def test_options_json_column_parsed(self) -> None:
        text = 'question_text,options,correct_answer\nQ1?,"{""A"": ""x"", ""B"": ""y""}",B\n'
        result = CSVParser().parse(text)
        assert result.records[0].question.options == {"A": "x", "B": "y"}

    def test_bad_page_is_warning_not_record_failure(self) -> None:
        text = "question_text,correct_answer,source_page\nQ1?,42,not-a-number\n"
        result = CSVParser().parse(text)
        assert len(result.records) == 1
        assert any("source_page" in w for w in result.warnings)

    def test_unknown_columns_reported_as_warning(self) -> None:
        text = "question_text,correct_answer,translator\nQ1?,42,Ann\n"
        result = CSVParser().parse(text)
        assert any("translator" in w for w in result.warnings)

    def test_too_many_columns_is_failure(self) -> None:
        text = "question_text,correct_answer\nQ1?,42,extra,columns\n"
        result = CSVParser().parse(text)
        assert not result.records
        assert "columns" in result.failures[0].error

    def test_missing_question_text_is_failure(self) -> None:
        text = "question_text,correct_answer\n,42\n"
        result = CSVParser().parse(text)
        assert not result.records
        assert "question_text" in result.failures[0].error


class TestTXTParser:
    def test_full_block_parses(self) -> None:
        text = (
            "Q: What is 20% of 50?\n"
            "A) 8\n"
            "B) 10\n"
            "C) 12\n"
            "D) 15\n"
            "Answer: B\n"
            "Source: Percent Book\n"
            "Page: 9\n"
            "ID: P-1\n"
        )
        result = TXTParser().parse(text)
        assert len(result.records) == 1
        assert not result.failures
        record = result.records[0].question
        assert record.question_text == "What is 20% of 50?"
        assert record.options == {"A": "8", "B": "10", "C": "12", "D": "15"}
        assert record.correct_answer == "B"
        assert record.source is not None
        assert record.source.page == 9
        assert record.source.question_id == "P-1"

    def test_numeric_question_omits_options(self) -> None:
        text = "Q: Solve 3x = 9\nAnswer: 3\n"
        result = TXTParser().parse(text)
        assert result.records[0].question.options == {}
        assert result.records[0].question.correct_answer == "3"

    def test_multiple_blocks(self) -> None:
        text = "Q: q1?\nAnswer: 1\n\nQ: q2?\nAnswer: 2\n\n\nQ: q3?\nAnswer: 3\n"
        result = TXTParser().parse(text)
        assert len(result.records) == 3
        assert not result.failures

    def test_multiline_question_continuation(self) -> None:
        text = "Q: A shopkeeper buys 20 articles\nand sells each at 10% profit.\nAnswer: 2\n"
        result = TXTParser().parse(text)
        assert result.records[0].question.question_text.startswith("A shopkeeper buys 20")
        assert "10% profit" in result.records[0].question.question_text

    def test_missing_answer_is_failure(self) -> None:
        text = "Q: No answer here?\nA) 1\n"
        result = TXTParser().parse(text)
        assert not result.records
        assert "correct_answer" in result.failures[0].error
        assert result.failures[0].location == "block 1"

    def test_labels_case_insensitive(self) -> None:
        text = "question: cased?\nans: A\n"
        result = TXTParser().parse(text)
        assert len(result.records) == 1
        assert result.records[0].question.correct_answer == "A"

    def test_unrecognized_line_after_answer_warns(self) -> None:
        text = "Q: q?\nAnswer: A\nstray note\n"
        result = TXTParser().parse(text)
        assert len(result.records) == 1
        assert any("stray note" in w for w in result.warnings)

    def test_empty_text_yields_warning_no_crash(self) -> None:
        result = TXTParser().parse("   \n\n")
        assert not result.records
        assert not result.failures
        assert result.warnings


class TestFormatDetection:
    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("q.jsonl", "jsonl"),
            ("q.ndjson", "jsonl"),
            ("q.csv", "csv"),
            ("q.txt", "txt"),
            ("q.text", "txt"),
        ],
    )
    def test_extension_detection(self, filename: str, expected: str) -> None:
        assert detect_format(Path(filename), "") == expected

    def test_unknown_extension_sniffs_jsonl(self) -> None:
        text = _line({"question_text": "Q?", "correct_answer": "1"})
        assert detect_format(Path("questions.dat"), text) == "jsonl"

    def test_unknown_extension_sniffs_csv(self) -> None:
        text = "q1,a,b,c\nq2,a,b,c\n"
        assert detect_format(Path("questions.dat"), text) == "csv"

    def test_unknown_extension_sniffs_txt(self) -> None:
        text = "Q: what?\nAnswer: 2\n"
        assert detect_format(Path("questions.dat"), text) == "txt"

    def test_undetectable_content_raises_with_hint(self) -> None:
        with pytest.raises(IngestionError, match="cannot detect format"):
            detect_format(Path("mystery.dat"), "just some prose without structure")

    @pytest.mark.parametrize("ext", [".pdf", ".docx"])
    def test_deferred_formats_raise_step9_hint(self, ext: str) -> None:
        with pytest.raises(IngestionError, match="Step 9"):
            detect_format(Path(f"manual{ext}"), "")

    def test_get_parser_unknown_format_raises(self) -> None:
        with pytest.raises(IngestionError, match="unknown format"):
            get_parser("yaml")

    def test_get_parser_returns_format_specific_instance(self) -> None:
        assert get_parser("csv").format_name == "csv"
        assert get_parser("jsonl").format_name == "jsonl"
        assert get_parser("txt").format_name == "txt"
