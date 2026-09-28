"""Integration tests: Typer CLI (Session C gate)."""

from typer.testing import CliRunner

from qme import __version__
from qme.cli import app

runner = CliRunner()


def test_help_exits_zero_and_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("ingest", "process", "review", "eval"):
        assert command in result.output


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.output


def test_stub_commands_exit_nonzero_with_step_hint() -> None:
    """Stubs fail loudly (never silently) and name their future step."""
    cases = [
        (["ingest", "--input", "in.jsonl", "--output", "out"], "Step 2"),
        (["process", "--input", "in.jsonl", "--output", "out"], "Step 8"),
        (
            ["review", "--input", "r.jsonl", "--action", "approve", "--output", "o.jsonl"],
            "Step 7",
        ),
        (["eval", "--gold", "g.jsonl", "--pred", "p.jsonl", "--output", "r.json"], "Step 11"),
    ]
    for argv, hint in cases:
        result = runner.invoke(app, argv)
        assert result.exit_code == 1, argv
        assert "Not implemented" in result.output
        assert hint in result.output


def test_review_action_validates_choices() -> None:
    result = runner.invoke(
        app, ["review", "--input", "r.jsonl", "--action", "bogus", "--output", "o.jsonl"]
    )
    assert result.exit_code != 0
