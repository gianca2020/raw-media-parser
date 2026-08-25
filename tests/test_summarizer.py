"""Unit tests for the Claude summarizer, using an injected fake client.

Covers the pure formatting helpers and the adapter's real behaviour: the request it
sends, that thinking blocks are excluded from the output, and that the deterministic
header is prepended to Claude's body.
"""

from __future__ import annotations

import types

import pytest

from raw_media_parser.errors import SummarizationError
from raw_media_parser.models import MediaMetadata, Transcript
from raw_media_parser.summarizer import (
    ClaudeSummarizer,
    _build_header,
    _extract_text,
    _format_date,
    _format_duration,
)


# --- pure helpers -----------------------------------------------------------------


def test_format_duration() -> None:
    assert _format_duration(None) is None
    assert _format_duration(0) is None
    assert _format_duration(65) == "1:05"
    assert _format_duration(3661) == "1:01:01"


def test_format_date() -> None:
    assert _format_date("20260102") == "2026-01-02"
    assert _format_date(None) is None
    assert _format_date("weird") == "weird"  # pass through the unexpected


def test_build_header_includes_known_facts() -> None:
    meta = MediaMetadata(
        title="My Talk",
        url="https://x/y",
        uploader="Chan",
        duration=3661,
        upload_date="20260102",
    )
    header = _build_header(meta)
    assert header.startswith("# My Talk")
    assert "**Channel:** Chan" in header
    assert "**Source:** https://x/y" in header
    assert "**Duration:** 1:01:01" in header
    assert "**Uploaded:** 2026-01-02" in header


def test_extract_text_ignores_thinking_blocks() -> None:
    response = types.SimpleNamespace(
        content=[
            types.SimpleNamespace(type="thinking", thinking="secret reasoning"),
            types.SimpleNamespace(type="text", text="## TL;DR\nGood."),
        ]
    )
    assert _extract_text(response) == "## TL;DR\nGood."


# --- the adapter, via a fake client -----------------------------------------------


class _FakeMessages:
    def __init__(self, *, blocks=None, raises=None):
        self._blocks = blocks
        self._raises = raises
        self.called_with: dict | None = None

    def create(self, **kwargs):
        self.called_with = kwargs
        if self._raises is not None:
            raise self._raises
        return types.SimpleNamespace(content=self._blocks)


def _fake_client(*, blocks=None, raises=None):
    return types.SimpleNamespace(messages=_FakeMessages(blocks=blocks, raises=raises))


def _text_block(text):
    return types.SimpleNamespace(type="text", text=text)


def _meta():
    return MediaMetadata(title="My Talk", url="https://x", uploader="Chan")


def test_summarize_prepends_header_and_sends_expected_request() -> None:
    client = _fake_client(
        blocks=[
            types.SimpleNamespace(type="thinking", thinking="reasoning"),
            _text_block("## TL;DR\nAll good."),
        ]
    )
    summarizer = ClaudeSummarizer(client=client, model="claude-opus-4-8", effort="low")

    markdown = summarizer.summarize(Transcript(text="the spoken words"), _meta())

    # Deterministic header + Claude's body, thinking excluded.
    assert markdown.startswith("# My Talk")
    assert "## TL;DR" in markdown
    assert "reasoning" not in markdown

    sent = client.messages.called_with
    assert sent["model"] == "claude-opus-4-8"
    assert sent["output_config"] == {"effort": "low"}
    assert sent["thinking"] == {"type": "adaptive"}
    assert "the spoken words" in sent["messages"][0]["content"]


def test_summarize_wraps_client_errors() -> None:
    client = _fake_client(raises=RuntimeError("boom"))
    with pytest.raises(SummarizationError):
        ClaudeSummarizer(client=client, model="m").summarize(
            Transcript(text="x"), _meta()
        )


def test_summarize_raises_when_no_text_returned() -> None:
    client = _fake_client(blocks=[types.SimpleNamespace(type="thinking", thinking="x")])
    with pytest.raises(SummarizationError):
        ClaudeSummarizer(client=client, model="m").summarize(
            Transcript(text="x"), _meta()
        )
