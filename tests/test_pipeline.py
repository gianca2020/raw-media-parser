"""Tests for the orchestration itself, using only fakes.

These prove the architecture works — stages run in order, data is handed off
correctly, the `mode` flag propagates, and the temp audio is cleaned up — without
any of the real adapters. That is the payoff of the ports-and-adapters design.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FakeFetcher, FakeSummarizer, FakeTranscriber, RecordingWriter

from raw_media_parser.models import MediaMetadata
from raw_media_parser.pipeline import Pipeline


def _meta() -> MediaMetadata:
    return MediaMetadata(title="Test Video", url="https://example.com/watch")


def test_pipeline_runs_stages_in_order_and_hands_off_data() -> None:
    writer = RecordingWriter()
    pipeline = Pipeline(
        FakeFetcher(_meta()),
        FakeTranscriber("the spoken words"),
        FakeSummarizer(),
        writer,
    )

    result = pipeline.run("https://example.com/watch")

    # The summarizer received both the metadata (title) and the transcript,
    # and the writer received the summarizer's output verbatim.
    assert writer.markdown is not None
    assert "Test Video" in writer.markdown
    assert "the spoken words" in writer.markdown
    assert writer.metadata is not None and writer.metadata.title == "Test Video"
    assert str(result).endswith("fake.md")


def test_pipeline_passes_mode_through() -> None:
    writer = RecordingWriter()
    Pipeline(
        FakeFetcher(_meta()), FakeTranscriber(), FakeSummarizer(), writer
    ).run("u", mode="detailed")

    assert writer.markdown is not None
    assert "mode=detailed" in writer.markdown


def test_pipeline_cleans_up_temp_audio() -> None:
    transcriber = FakeTranscriber()
    Pipeline(
        FakeFetcher(_meta()), transcriber, FakeSummarizer(), RecordingWriter()
    ).run("u")

    # The transcriber saw a real file mid-run; once run() returns, the temp
    # directory (and the audio in it) must be gone.
    assert transcriber.seen_path is not None
    assert not transcriber.seen_path.exists()
