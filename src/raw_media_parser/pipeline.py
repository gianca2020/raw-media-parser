"""The orchestrator: url -> Markdown file.

This is the whole application logic in one place, and it is intentionally tiny.
It knows the *order* of the stages and owns the temp-directory lifecycle, but it
knows nothing about yt-dlp, Groq, or Anthropic — it only sees the four ports.
Everything concrete is passed in (dependency injection), so this class can be
exercised end-to-end with fakes and never a network call.

Two surfaces consume it: the CLI (`parse.py`) and the local web server
(`serve.py`). Neither owns any parsing logic; they differ only in how they
render the `ParseResult`.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable, Optional

from .models import ParseResult
from .ports import AudioFetcher, MarkdownWriter, Summarizer, Transcriber

# Stage names emitted to `on_stage`. Public because the web UI labels them.
STAGE_FETCH = "fetch"
STAGE_TRANSCRIBE = "transcribe"
STAGE_SUMMARIZE = "summarize"
STAGE_WRITE = "write"
STAGES = (STAGE_FETCH, STAGE_TRANSCRIBE, STAGE_SUMMARIZE, STAGE_WRITE)

# Called with a stage name just before that stage starts. Kept to a plain
# callable so the core needs no event library and no async.
StageCallback = Callable[[str], None]


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

    def run(
        self,
        url: str,
        mode: str = "brief",
        on_stage: Optional[StageCallback] = None,
    ) -> ParseResult:
        """Fetch → transcribe → summarize → write. Returns everything produced.

        The downloaded audio is a throwaway intermediate, so it lives in a
        TemporaryDirectory that is deleted when this method returns — even on
        error — thanks to the context manager. Nothing downstream needs the file
        once it has been transcribed.

        `on_stage`, if given, is called with each stage's name just before that
        stage runs. It exists so a caller can report progress during a run that
        takes minutes; passing nothing keeps the plain synchronous behaviour.
        """
        notify = on_stage or (lambda _stage: None)

        with tempfile.TemporaryDirectory(prefix="rmp-") as tmp:
            notify(STAGE_FETCH)
            artifact = self._fetcher.fetch(url, Path(tmp))

            notify(STAGE_TRANSCRIBE)
            transcript = self._transcriber.transcribe(artifact.path)

            notify(STAGE_SUMMARIZE)
            markdown = self._summarizer.summarize(
                transcript, artifact.metadata, mode=mode
            )

            notify(STAGE_WRITE)
            path = self._writer.write(markdown, artifact.metadata)

            return ParseResult(
                path=path,
                markdown=markdown,
                transcript=transcript,
                metadata=artifact.metadata,
            )
