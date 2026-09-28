"""Failure tests: unsupported formats are rejected with actionable errors."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from qme.cli import app
from qme.core.exceptions import IngestionError
from qme.ingestion import get_parser, ingest_file

runner = CliRunner()


def test_pdf_input_rejected_with_step_hint(tmp_path: Path) -> None:
    path = tmp_path / "manual.pdf"
    path.write_bytes(b"%PDF-1.4 not really")
    result = runner.invoke(
        app, ["ingest", "--input", str(path), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 1
    assert "Step 9" in result.output


def test_docx_input_rejected_with_step_hint(tmp_path: Path) -> None:
    path = tmp_path / "manual.docx"
    path.write_bytes(b"PK not really a docx")
    result = runner.invoke(
        app, ["ingest", "--input", str(path), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 1
    assert "Step 9" in result.output


def test_format_flag_pdf_rejected_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    path.write_text('{"question_text": "q", "correct_answer": "1"}\n', encoding="utf-8")
    result = runner.invoke(
        app,
        ["ingest", "--input", str(path), "--output", str(tmp_path / "out"), "--format", "pdf"],
    )
    assert result.exit_code == 1
    assert "Step 9" in result.output


def test_format_flag_unknown_value_rejected(tmp_path: Path) -> None:
    path = tmp_path / "questions.jsonl"
    path.write_text('{"question_text": "q", "correct_answer": "1"}\n', encoding="utf-8")
    result = runner.invoke(
        app,
        ["ingest", "--input", str(path), "--output", str(tmp_path / "out"), "--format", "yaml"],
    )
    assert result.exit_code == 1
    assert "unknown format" in result.output


def test_undetectable_file_fails_with_format_hint(tmp_path: Path) -> None:
    path = tmp_path / "mystery.dat"
    path.write_text("just prose with no structure at all\n", encoding="utf-8")
    result = runner.invoke(
        app, ["ingest", "--input", str(path), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 1
    assert "--format" in result.output


def test_format_override_bypasses_detection(tmp_path: Path) -> None:
    """A wrong extension still works when --format is explicit."""
    path = tmp_path / "questions.txt"
    path.write_text('{"question_text": "q", "correct_answer": "1"}\n', encoding="utf-8")
    result = ingest_file(path, fmt="jsonl")
    assert len(result.questions) == 1
    assert result.format == "jsonl"


@pytest.mark.parametrize("fmt", ["pdf", "docx"])
def test_get_parser_deferred_formats_raise(fmt: str) -> None:
    with pytest.raises(IngestionError, match="Step 9"):
        get_parser(fmt)
