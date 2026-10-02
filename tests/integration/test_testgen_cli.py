"""CLI wiring for ``qme testgen`` / ``qme practice`` (Typer runner, offline)."""

from typer.testing import CliRunner

from qme.cli import app
from tests.testgen_fixtures import write_bank

runner = CliRunner()


def test_testgen_writes_json_and_markdown(tmp_path):
    blueprint = write_bank(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "testgen",
            "--blueprint",
            str(blueprint),
            "--output",
            str(out),
            "--count",
            "3",
            "--seed",
            "1",
            "--title",
            "CLI Paper",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(list(out.glob("T-*.json"))) == 1
    assert len(list(out.glob("T-*.md"))) == 1
    assert "3 questions" in result.output


def test_testgen_contract_violation_exits_1(tmp_path):
    blueprint = write_bank(tmp_path, contract_overrides={"output_fields": ["test_id"]})
    result = runner.invoke(
        app,
        ["testgen", "--blueprint", str(blueprint), "--output", str(tmp_path / "out")],
    )
    assert result.exit_code == 1


def test_testgen_unknown_filter_exits_1(tmp_path):
    blueprint = write_bank(tmp_path)
    result = runner.invoke(
        app,
        [
            "testgen",
            "--blueprint",
            str(blueprint),
            "--output",
            str(tmp_path / "out"),
            "--chapter",
            "Nonexistent",
        ],
    )
    assert result.exit_code == 1


def test_practice_writes_outputs(tmp_path):
    blueprint = write_bank(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "practice",
            "--blueprint",
            str(blueprint),
            "--output",
            str(out),
            "--count",
            "2",
            "--seed",
            "4",
            "--mode",
            "mixed",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(list(out.glob("P-*.json"))) == 1
    assert len(list(out.glob("P-*.md"))) == 1


def test_practice_invalid_difficulty_exits_1(tmp_path):
    blueprint = write_bank(tmp_path)
    result = runner.invoke(
        app,
        [
            "practice",
            "--blueprint",
            str(blueprint),
            "--output",
            str(tmp_path / "out"),
            "--difficulty",
            "brutal",
        ],
    )
    assert result.exit_code == 1
