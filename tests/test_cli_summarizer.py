"""Unit tests for the Claude Code CLI summarizer, using an injected fake runner.

No subprocess, no `claude` CLI, no subscription usage: we swap the runner for a fake and
check the adapter's real behaviour — it feeds the transcript in, prepends the
deterministic header to the model's body, and translates failures into
SummarizationError. The JSON-parsing helper is covered directly.
"""

from __future__ import annotations

import pytest

from raw_media_parser.cli_summarizer import ClaudeCliSummarizer, _extract_result
from raw_media_parser.errors import SummarizationError
from raw_media_parser.models import MediaMetadata, Transcript


def _meta() -> MediaMetadata:
    return MediaMetadata(title="My Talk", url="https://x", uploader="Chan")


def test_summarize_prepends_header_and_passes_transcript() -> None:
    captured: dict = {}

    def fake_runner(*, model, stdin_text):
        captured["model"] = model
        captured["stdin_text"] = stdin_text
        return "## TL;DR\nAll good."

    summarizer = ClaudeCliSummarizer(model="opus", runner=fake_runner)
    markdown = summarizer.summarize(Transcript(text="the spoken words"), _meta())

    assert markdown.startswith("# My Talk")               # deterministic header
    assert "## TL;DR" in markdown                          # model's body
    assert captured["model"] == "opus"
    assert "the spoken words" in captured["stdin_text"]    # transcript reached the runner


def test_summarize_raises_when_body_empty() -> None:
    summarizer = ClaudeCliSummarizer(runner=lambda **_: "   ")
    with pytest.raises(SummarizationError):
        summarizer.summarize(Transcript(text="x"), _meta())


def test_summarize_wraps_runner_errors() -> None:
    def boom(**_):
        raise RuntimeError("cli exploded")

    summarizer = ClaudeCliSummarizer(runner=boom)
    with pytest.raises(SummarizationError):
        summarizer.summarize(Transcript(text="x"), _meta())


def test_extract_result_reads_result_field() -> None:
    assert _extract_result('{"is_error": false, "result": "hello"}') == "hello"


def test_extract_result_raises_on_error_flag() -> None:
    with pytest.raises(SummarizationError):
        _extract_result('{"is_error": true, "result": "nope"}')


def test_extract_result_raises_on_bad_json() -> None:
    with pytest.raises(SummarizationError):
        _extract_result("not json at all")
