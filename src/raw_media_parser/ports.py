"""Ports: the contracts the pipeline depends on.

These are the seams of the system. The `Pipeline` (core) talks only to these
`Protocol`s, never to yt-dlp, Groq, or Anthropic directly. Each concrete adapter
(YtDlpFetcher, GroqTranscriber, ClaudeSummarizer, MarkdownWriter) implements one
port and is injected at the edges (the CLI). That inversion is what lets us swap a
provider, or test the whole pipeline with in-memory fakes, without touching core code.

`Protocol` (structural typing) means an adapter satisfies a port just by having the
right method shape — it does not need to import or subclass anything here, so the
adapters stay decoupled from the core.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import AudioArtifact, MediaMetadata, Transcript


class AudioFetcher(Protocol):
    """url -> a local audio file plus what we know about the source."""

    def fetch(self, url: str, dest_dir: Path) -> AudioArtifact:
        """Download audio for `url` into `dest_dir` and describe it.

        `dest_dir` is owned by the caller (the pipeline hands over a temp dir it
        will clean up), so the fetcher never has to worry about lifecycle.
        """
        ...


class Transcriber(Protocol):
    """audio file -> spoken text."""

    def transcribe(self, audio_path: Path) -> Transcript:
        ...


class Summarizer(Protocol):
    """transcript (+ metadata) -> a Markdown brief."""

    def summarize(
        self, transcript: Transcript, metadata: MediaMetadata, mode: str = "brief"
    ) -> str:
        """`mode` is the seam for a future "detailed" option; only "brief" today."""
        ...


class MarkdownWriter(Protocol):
    """Markdown text -> a file on disk; returns where it landed."""

    def write(self, markdown: str, metadata: MediaMetadata) -> Path:
        ...
