"""Immutable data passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaMetadata:
    """Facts about the source media, extracted alongside the audio."""

    title: str
    url: str
    uploader: str | None = None
    duration: float | None = None
    upload_date: str | None = None  # yt-dlp format: "YYYYMMDD"


@dataclass(frozen=True)
class AudioArtifact:
    """A downloaded audio file plus what we know about its source."""

    path: Path
    metadata: MediaMetadata


@dataclass(frozen=True)
class Transcript:
    """The spoken text of the audio."""

    text: str


@dataclass(frozen=True)
class ParseResult:
    """Everything one pipeline run produced.

    The pipeline used to return just the output path, which was all the CLI
    needed. The web surface also wants to *show* the brief and the transcript
    without re-reading the file, so the run now hands back the whole set. The
    transcript in particular was previously discarded as an intermediate.
    """

    path: Path
    markdown: str
    transcript: Transcript
    metadata: MediaMetadata
