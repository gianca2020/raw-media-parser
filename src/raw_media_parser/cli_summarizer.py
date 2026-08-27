"""Summarization adapter: implements the `Summarizer` port via the Claude Code CLI.

Responsibility: transcript (+ metadata) -> a Markdown brief — using the user's Claude
Code SUBSCRIPTION (Max/Pro) instead of the Anthropic API. There is no API key and no
per-token billing; the call runs through `claude --print` (headless mode) and counts
against the subscription's usage limits.

Prerequisite: the `claude` CLI must be installed and logged in (run `claude` once and
complete `/login`). Everything the model is asked is identical to the API-based
`ClaudeSummarizer` — same system prompt, same deterministic metadata header — only the
transport differs, so the two are interchangeable behind the `Summarizer` port.

The subprocess call is injectable (`runner=`) so the adapter is unit-testable with a
fake — no CLI, no subscription usage.
"""

from __future__ import annotations

import json
import subprocess

from .errors import SummarizationError
from .models import MediaMetadata, Transcript
from .prompts import SYSTEM_PROMPT, build_user_content
from .summarizer import _build_header  # reuse the deterministic header formatter

DEFAULT_MODEL = "opus"  # Claude Code model alias -> the subscription's Opus

# The real instructions live in SYSTEM_PROMPT; this just points the model at stdin.
_DIRECTIVE = (
    "Summarize the transcript provided on stdin, following your system-prompt "
    "instructions exactly. Output only the Markdown brief — no preamble."
)

# Long enough for the biggest transcripts; a stuck CLI shouldn't hang the pipeline.
_TIMEOUT_SECONDS = 300


class ClaudeCliSummarizer:
    """`Summarizer` backed by the Claude Code CLI (`claude --print`) on the subscription."""

    def __init__(self, *, model: str = DEFAULT_MODEL, runner=None) -> None:
        self._model = model
        self._run = runner if runner is not None else _run_claude

    def summarize(
        self, transcript: Transcript, metadata: MediaMetadata, mode: str = "brief"
    ) -> str:
        # `mode` is the reserved seam for a future "detailed" option; only "brief" today.
        user_content = build_user_content(
            transcript.text, title=metadata.title, uploader=metadata.uploader
        )
        try:
            body = self._run(model=self._model, stdin_text=user_content)
        except SummarizationError:
            raise
        except Exception as exc:  # translate any subprocess/IO failure at the boundary
            raise SummarizationError(f"summarization failed: {exc}") from exc

        body = body.strip()
        if not body:
            raise SummarizationError("summarizer returned no text")
        return f"{_build_header(metadata)}\n{body}\n"


def _run_claude(*, model: str, stdin_text: str) -> str:
    """Run `claude --print` headlessly and return the model's text result.

    Uses the user's Claude Code subscription auth (no API key). Tools are disabled and
    the turn capped so this is a single, pure text completion, not an agent loop.
    """
    cmd = [
        "claude",
        "--print", _DIRECTIVE,
        "--model", model,
        "--system-prompt", SYSTEM_PROMPT,
        "--output-format", "json",
        "--max-turns", "1",
        "--allowed-tools", "",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise SummarizationError(
            "the `claude` CLI was not found — install Claude Code and log in "
            "(https://claude.com/claude-code)."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SummarizationError("the `claude` CLI timed out after 5 minutes.") from exc

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise SummarizationError(f"`claude` exited {proc.returncode}: {detail}")

    return _extract_result(proc.stdout)


def _extract_result(stdout: str) -> str:
    """Pull the `result` text out of `claude --output-format json` output."""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SummarizationError(
            f"could not parse `claude` output as JSON: {exc}"
        ) from exc
    if payload.get("is_error"):
        raise SummarizationError(
            f"`claude` reported an error: {payload.get('result') or payload}"
        )
    result = payload.get("result")
    if not isinstance(result, str):
        raise SummarizationError("`claude` returned no text result.")
    return result
