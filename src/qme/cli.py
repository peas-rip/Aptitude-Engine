"""QME command-line interface.

Command shapes follow ``docs/API_CONTRACTS.md`` section 5. ``ingest`` is
implemented (Step 2); the rest remain loud stubs until their steps land.
"""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError as PydanticValidationError

from qme import __version__
from qme.core.constants import ReviewAction
from qme.core.exceptions import IngestionError
from qme.ingestion import ingest_file
from qme.output import write_jsonl
from qme.testgen import generate_practice, generate_test, load_bank
from qme.testgen.errors import TestGenError
from qme.testgen.render import practice_to_markdown, test_to_markdown
from qme.testgen.schemas import PracticeRequest, Selection, TestRequest

app = typer.Typer(
    name="qme",
    help="Question Metadata Engine - transform raw aptitude questions into structured metadata.",
    invoke_without_command=True,  # no-args help handled in the callback (exit 0)
    add_completion=False,
)


def _not_implemented(step: str) -> None:
    typer.echo(f"Not implemented yet - scheduled for {step}.", err=True)
    raise typer.Exit(code=1)


def _version_callback(value: bool) -> None:
    """Eager callback: fires during parsing, before command resolution."""
    if value:
        typer.echo(f"qme {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def ingest(
    input: Annotated[Path, typer.Option("--input", help="Input file path.")],
    output: Annotated[Path, typer.Option("--output", help="Output directory.")],
    format: Annotated[
        str | None,
        typer.Option(
            "--format",
            help="jsonl | csv | txt | pdf | docx (default: detect from file).",
        ),
    ] = None,
) -> None:
    """Parse a raw file into normalized questions (FE-001, Step 2)."""
    try:
        result = ingest_file(input, format)
    except IngestionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    questions_path = output / "normalized.jsonl"
    written = write_jsonl(questions_path, result.questions)
    typer.echo(f"{written} questions -> {questions_path}")

    if result.failures:
        failures_path = output / "ingest_failures.jsonl"
        write_jsonl(failures_path, result.failures)
        typer.echo(
            f"{len(result.failures)} failed records -> {failures_path}",
            err=True,
        )
    if written == 0:
        typer.echo("Error: no valid questions produced", err=True)
        raise typer.Exit(code=1)


@app.command()
def process(
    input: Annotated[Path, typer.Option("--input", help="Input file path.")],
    output: Annotated[Path, typer.Option("--output", help="Output directory.")],
    checkpoint_dir: Annotated[
        Path, typer.Option("--checkpoint-dir", help="Checkpoint directory for resume.")
    ] = Path("./data/checkpoints"),
    config: Annotated[
        Path | None, typer.Option("--config", help="Batch config JSON file.")
    ] = None,
) -> None:
    """Run the metadata pipeline over a batch file (FE-007, Step 8)."""
    _not_implemented("Step 8: Pipeline Orchestration")


@app.command()
def review(
    input: Annotated[Path, typer.Option("--input", help="review.jsonl path.")],
    action: Annotated[ReviewAction, typer.Option("--action", help="approve | reject | edit")],
    output: Annotated[Path, typer.Option("--output", help="Output file path.")],
) -> None:
    """Resolve human-review queue items (FE-009, Step 7)."""
    _not_implemented("Step 7: Validation Pipeline + review queue")


@app.command()
def eval(
    gold: Annotated[Path, typer.Option("--gold", help="Gold-standard JSONL.")],
    pred: Annotated[Path, typer.Option("--pred", help="Predictions JSONL.")],
    output: Annotated[Path, typer.Option("--output", help="Report JSON path.")],
) -> None:
    """Compare predictions against the gold standard (Step 11)."""
    _not_implemented("Step 11: Evaluation Harness")


def _write_outputs(output: Path, stem: str, payload_json: str, markdown: str, fmt: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if fmt in ("json", "both"):
        path = output / f"{stem}.json"
        path.write_text(payload_json, encoding="utf-8")
        typer.echo(f"json -> {path}")
    if fmt in ("md", "both"):
        path = output / f"{stem}.md"
        path.write_text(markdown, encoding="utf-8")
        typer.echo(f"md -> {path}")


@app.command()
def testgen(
    blueprint: Annotated[Path, typer.Option("--blueprint", help="aptitude_test_blueprint.json path.")],
    output: Annotated[Path, typer.Option("--output", help="Output directory.")],
    count: Annotated[int, typer.Option("--count", min=1, help="Questions to select.")] = 10,
    chapter: Annotated[str | None, typer.Option("--chapter")] = None,
    topic: Annotated[str | None, typer.Option("--topic")] = None,
    difficulty: Annotated[str | None, typer.Option("--difficulty", help="easy | medium | hard")] = None,
    seed: Annotated[int | None, typer.Option("--seed", help="Deterministic seed.")] = None,
    test_id: Annotated[str | None, typer.Option("--test-id")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    fmt: Annotated[str, typer.Option("--format", help="json | md | both")] = "both",
) -> None:
    """Assemble a blueprint-conformant test from the external agent's bank."""
    try:
        bank = load_bank(blueprint)
        request = TestRequest(
            test_id=test_id,
            title=title,
            seed=seed,
            selections=[
                Selection(
                    count=count,
                    chapter=chapter,
                    topic=topic,
                    difficulty=difficulty,  # type: ignore[arg-type]
                )
            ],
        )
        test = generate_test(bank, request)
    except (TestGenError, PydanticValidationError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _write_outputs(
        output,
        test.test_id,
        test.model_dump_json(indent=2),
        test_to_markdown(test),
        fmt,
    )
    typer.echo(
        f"test {test.test_id}: {test.coverage.total} questions, "
        f"{sum(s.shortfall for s in test.shortages)} short"
    )


@app.command()
def practice(
    blueprint: Annotated[Path, typer.Option("--blueprint", help="aptitude_test_blueprint.json path.")],
    output: Annotated[Path, typer.Option("--output", help="Output directory.")],
    count: Annotated[int, typer.Option("--count", min=1, help="Questions in the set.")] = 10,
    chapter: Annotated[str | None, typer.Option("--chapter")] = None,
    topic: Annotated[str | None, typer.Option("--topic")] = None,
    difficulty: Annotated[str | None, typer.Option("--difficulty", help="easy | medium | hard")] = None,
    mode: Annotated[str, typer.Option("--mode", help="progressive | mixed")] = "progressive",
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    practice_id: Annotated[str | None, typer.Option("--practice-id")] = None,
    title: Annotated[str | None, typer.Option("--title")] = None,
    fmt: Annotated[str, typer.Option("--format", help="json | md | both")] = "both",
) -> None:
    """Build a practice set (easy->hard progressive or seeded mixed order)."""
    try:
        bank = load_bank(blueprint)
        request = PracticeRequest(
            practice_id=practice_id,
            title=title,
            seed=seed,
            count=count,
            chapter=chapter,
            topic=topic,
            difficulty=difficulty,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
        )
        practice_set = generate_practice(bank, request)
    except (TestGenError, PydanticValidationError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _write_outputs(
        output,
        practice_set.practice_id,
        practice_set.model_dump_json(indent=2),
        practice_to_markdown(practice_set),
        fmt,
    )
    typer.echo(
        f"practice {practice_set.practice_id}: {practice_set.coverage.total} questions, "
        f"mode={practice_set.mode}"
    )
