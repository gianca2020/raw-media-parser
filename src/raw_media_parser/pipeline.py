"""The orchestrator: url -> Markdown file.

This is the whole application logic in one place, and it is intentionally tiny.
It knows the *order* of the stages and owns the temp-directory lifecycle, but it
knows nothing about yt-dlp, Groq, or Anthropic — it only sees the four ports.
Everything concrete is passed in (dependency injection), so this class can be
exercised end-to-end with fakes and never a network call.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from .ports import AudioFetcher, MarkdownWriter, Summarizer, Transcriber


class Pipeline:
    def __init__(
        self,
        fetcher: AudioFetcher,
        transcriber: Transcriber,
        summarizer: Summarizer,
        writer: MarkdownWriter,
    ) -> None:
        self._fetcher = fetcher
        self._transcriber = transcriber
        self._summarizer = summarizer
        self._writer = writer

    def run(self, url: str, mode: str = "brief") -> Path:
        """Fetch → transcribe → summarize → write. Returns the output file path.

        The downloaded audio is a throwaway intermediate, so it lives in a
        TemporaryDirectory that is deleted when this method returns — even on
        error — thanks to the context manager. Nothing downstream needs the file
        once it has been transcribed.
        """
        with tempfile.TemporaryDirectory(prefix="rmp-") as tmp:
            artifact = self._fetcher.fetch(url, Path(tmp))
            transcript = self._transcriber.transcribe(artifact.path)
            markdown = self._summarizer.summarize(
                transcript, artifact.metadata, mode=mode
            )
            return self._writer.write(markdown, artifact.metadata)
