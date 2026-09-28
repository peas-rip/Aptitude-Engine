"""Integration tests: `qme ingest` end-to-end over sample files (M2 gate)."""

import json
from pathlib import Path

from typer.testing import CliRunner

from qme.cli import app
from qme.core.models import NormalizedQuestion
from qme.ingestion import ingest_file

runner = CliRunner()

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_jsonl_sample_ingests_via_cli(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["ingest", "--input", str(SAMPLES / "sample_questions.jsonl"), "--output", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    rows = _read_jsonl(tmp_path / "normalized.jsonl")
    assert len(rows) == 12
    for row in rows:
        NormalizedQuestion.model_validate(row)  # exact contract schema


def test_csv_sample_ingests_via_cli(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["ingest", "--input", str(SAMPLES / "sample_questions.csv"), "--output", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    rows = _read_jsonl(tmp_path / "normalized.jsonl")
    assert len(rows) == 5
    assert all(NormalizedQuestion.model_validate(row) for row in rows)


def test_txt_sample_ingests_via_cli(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["ingest", "--input", str(SAMPLES / "sample_questions.txt"), "--output", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    rows = _read_jsonl(tmp_path / "normalized.jsonl")
    assert len(rows) == 4
    assert all(NormalizedQuestion.model_validate(row) for row in rows)


def test_output_dir_created_when_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "out"
    result = runner.invoke(
        app,
        ["ingest", "--input", str(SAMPLES / "sample_questions.jsonl"), "--output", str(nested)],
    )
    assert result.exit_code == 0, result.output
    assert (nested / "normalized.jsonl").is_file()


def test_provenance_complete_on_every_output() -> None:
    """FE-008 acceptance: complete provenance on every ingested question."""
    result = ingest_file(SAMPLES / "sample_questions.jsonl")
    for question in result.questions:
        assert question.source.name
        assert question.source.type
        assert question.source.identifier


def test_all_three_formats_normalize_identical_sample_sets(tmp_path: Path) -> None:
    counts = {
        fmt: len(ingest_file(SAMPLES / f"sample_questions.{fmt}").questions)
        for fmt in ("jsonl", "csv", "txt")
    }
    assert counts == {"jsonl": 12, "csv": 5, "txt": 4}


def test_unknown_extension_detected_by_content(tmp_path: Path) -> None:
    source = (SAMPLES / "sample_questions.jsonl").read_text(encoding="utf-8")
    disguised = tmp_path / "questions.dat"
    disguised.write_text(source, encoding="utf-8")
    result = ingest_file(disguised)
    assert result.format == "jsonl"
    assert len(result.questions) == 12


def test_hundred_questions_acceptance(tmp_path: Path) -> None:
    """FE-001 acceptance: 100 clean questions -> 100 NormalizedQuestion."""
    path = tmp_path / "batch.jsonl"
    records = [
        json.dumps(
            {
                "question_text": f"Question {i}: what is {i} + 0?",
                "options": {"A": str(i), "B": str(i + 1), "C": str(i + 2), "D": str(i + 3)},
                "correct_answer": "A",
                "source": {"name": "batch", "type": "jsonl", "identifier": "batch.jsonl"},
            }
        )
        for i in range(100)
    ]
    path.write_text("\n".join(records) + "\n", encoding="utf-8")
    result = ingest_file(path)
    assert not result.failures
    assert len(result.questions) == 100


def test_partial_failures_written_to_failures_file(tmp_path: Path) -> None:
    input_path = tmp_path / "mixed.jsonl"
    good = json.dumps({"question_text": "Q1?", "correct_answer": "42"})
    bad_json = "{oops"
    bad_answer = json.dumps(
        {"question_text": "Q2?", "options": {"A": "x", "B": "y"}, "correct_answer": "Z"}
    )
    input_path.write_text("\n".join([good, bad_json, bad_answer]) + "\n", encoding="utf-8")

    result = runner.invoke(
        app, ["ingest", "--input", str(input_path), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0, result.output
    assert "1 questions" in result.output
    assert "2 failed records" in result.output

    questions = _read_jsonl(tmp_path / "out" / "normalized.jsonl")
    failures = _read_jsonl(tmp_path / "out" / "ingest_failures.jsonl")
    assert len(questions) == 1
    assert len(failures) == 2
    stages = {f["stage"] for f in failures}
    assert stages == {"parse", "normalize"}
    assert all(f["location"] and f["error"] for f in failures)
