"""QME command-line interface.

Command shapes follow ``docs/API_CONTRACTS.md`` section 5. In M1 these are
stubs; each prints which implementation step will fill it in.
"""

from pathlib import Path
from typing import Annotated

import typer

from qme import __version__
from qme.core.constants import ReviewAction

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
    format: Annotated[str, typer.Option("--format", help="jsonl | csv | txt | pdf | docx")] = "jsonl",
) -> None:
    """Parse a raw file into normalized questions (FE-001, Step 2)."""
    _not_implemented("Step 2: Ingestion Core")


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
