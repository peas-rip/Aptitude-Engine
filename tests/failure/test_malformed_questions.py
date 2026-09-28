"""Failure tests: malformed input never crashes and never fails silently (FE-001)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from qme.cli import app
from qme.ingestion import ingest_file

runner = CliRunner()


def _ingest_via_cli(input_path: Path, tmp_path: Path):
    return runner.invoke(
        app,
        ["ingest", "--input", str(input_path), "--output", str(tmp_path / "out")],
    )


def test_malformed_line_skipped_with_location(tmp_path: Path) -> None:
    path = tmp_path / "broken.jsonl"
    good = json.dumps({"question_text": "Q?", "correct_answer": "5"})
    path.write_text(f'{{"question_text": "no close"\n{good}\n', encoding="utf-8")
    result = ingest_file(path)
    assert len(result.questions) == 1
    assert len(result.failures) == 1
    assert result.failures[0].stage == "parse"
    assert result.failures[0].location == "line 1"


def test_all_records_invalid_exits_one(tmp_path: Path) -> None:
    path = tmp_path / "all_bad.jsonl"
    path.write_text("{oops\n{still broken\n", encoding="utf-8")
    result = _ingest_via_cli(path, tmp_path)
    assert result.exit_code == 1
    assert "no valid questions" in result.output


def test_invalid_utf8_rejected_with_context(tmp_path: Path) -> None:
    path = tmp_path / "latin1.csv"
    path.write_bytes(b"question_text,correct_answer\ncaf\xe9,42\n")
    result = _ingest_via_cli(path, tmp_path)
    assert result.exit_code == 1
    assert "not valid UTF-8" in result.output


def test_missing_file_reports_not_found(tmp_path: Path) -> None:
    result = _ingest_via_cli(tmp_path / "does_not_exist.jsonl", tmp_path)
    assert result.exit_code == 1
    assert "input file not found" in result.output


def test_oversized_file_rejected(tmp_path: Path) -> None:
    path = tmp_path / "huge.jsonl"
    path.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    result = _ingest_via_cli(path, tmp_path)
    assert result.exit_code == 1
    assert "limit is" in result.output


def test_answer_not_in_options_goes_to_failures_not_output(tmp_path: Path) -> None:
    path = tmp_path / "bad_answer.jsonl"
    record = json.dumps(
        {"question_text": "Pick one", "options": {"A": "x", "B": "y"}, "correct_answer": "Q"}
    )
    path.write_text(record + "\n", encoding="utf-8")
    result = ingest_file(path)
    assert not result.questions
    assert result.failures[0].stage == "normalize"
    assert "does not match" in result.failures[0].error
    assert "Pick one" in result.failures[0].raw  # raw context kept for debugging


def test_directory_as_input_rejected(tmp_path: Path) -> None:
    result = _ingest_via_cli(tmp_path, tmp_path)
    assert result.exit_code == 1
    assert "not a file" in result.output


def test_empty_file_exits_one(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("", encoding="utf-8")
    result = _ingest_via_cli(path, tmp_path)
    assert result.exit_code == 1
    assert "no valid questions" in result.output
