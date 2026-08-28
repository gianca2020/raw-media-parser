"""Command-line entry point and composition root.

This is the *only* place the concrete adapters are named. It reads settings from the
environment (loading a local `.env` if present), constructs one adapter per port,
injects them into the `Pipeline`, runs it, and maps our domain errors onto clean
messages and exit codes.

The summary runs through the Claude Code CLI on your Max/Pro subscription (no Anthropic
API key); transcription uses Groq. To swap either provider, change the one line that
names its adapter — nothing else moves.

Design notes:
- Progress and errors go to **stderr**; the resulting file path is the only thing on
  **stdout**, so `parse <url>` composes in a shell (e.g. `open "$(parse <url>)"`).
- Exit codes: 0 success, 1 a stage failed, 2 misconfiguration (e.g. missing key).
"""

from typing import Optional
from pathlib import Path

import typer
from dotenv import load_dotenv

from .cli_summarizer import ClaudeCliSummarizer
from .config import Settings
from .errors import ParserError
from .fetcher import YtDlpFetcher
from .pipeline import Pipeline
from .transcriber import GroqTranscriber
from .writer import MarkdownWriter

app = typer.Typer(
    add_completion=False,
    help="Turn a video URL into a concise Markdown brief of its audio.",
)


@app.command()
def parse(
    url: str = typer.Argument(
        ..., help="Video URL (YouTube, TikTok, Instagram, X)."
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o",
        help="Directory for the .md file (default: ./output or $RMP_OUTPUT_DIR).",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Claude Code model for the summary: opus, sonnet, or haiku (default: opus).",
    ),
) -> None:
    """Fetch a video's audio, transcribe it, and write a Markdown brief."""
    load_dotenv()

    try:
        settings = Settings.from_env()
    except ParserError as exc:
        typer.secho(f"Config error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    pipeline = Pipeline(
        fetcher=YtDlpFetcher(),
        transcriber=GroqTranscriber(settings.groq_api_key),
        # Summary via the Claude Code CLI on your subscription — no Anthropic API key.
        summarizer=ClaudeCliSummarizer(model=model or "opus"),
        writer=MarkdownWriter(output_dir or settings.output_dir),
    )

    typer.secho(f"Processing {url} …", fg=typer.colors.CYAN, err=True)

    def show_stage(stage: str) -> None:
        typer.secho(f"  … {stage}", fg=typer.colors.BLUE, err=True)

    try:
        result = pipeline.run(url, on_stage=show_stage)
    except ParserError as exc:
        typer.secho(f"{type(exc).__name__}: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"✓ wrote {result.path}", fg=typer.colors.GREEN, err=True)
    typer.echo(str(result.path))  # stdout = the path, so the command is pipeable
