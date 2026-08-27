"""In-memory fakes that satisfy the ports.

Because the pipeline depends only on the port protocols, these fakes let us test
the real orchestration (stage order, data hand-off, temp-dir cleanup) with no
network, no API keys, and no ffmpeg. Each fake also asserts a little about how it
was called, so the tests catch wiring mistakes.
"""

from __future__ import annotations

from pathlib import Path

from raw_media_parser.models import AudioArtifact, MediaMetadata, Transcript


class FakeFetcher:
    """Writes a stand-in audio file into the dest dir the pipeline provides."""

    def __init__(self, metadata: MediaMetadata) -> None:
        self._metadata = metadata

    def fetch(self, url: str, dest_dir: Path) -> AudioArtifact:
        path = Path(dest_dir) / "audio.mp3"
        path.write_bytes(b"fake-audio-bytes")
        return AudioArtifact(path=path, metadata=self._metadata)


class FakeTranscriber:
    """Returns canned text, but first proves the fetched audio actually exists."""

    def __init__(self, text: str = "hello world") -> None:
        self._text = text
        self.seen_path: Path | None = None

    def transcribe(self, audio_path: Path) -> Transcript:
        self.seen_path = Path(audio_path)
        assert self.seen_path.exists(), "transcriber ran before the audio existed"
        return Transcript(text=self._text)


class FakeSummarizer:
    """Echoes metadata + transcript + mode so tests can assert what flowed through."""

    def summarize(
        self, transcript: Transcript, metadata: MediaMetadata, mode: str = "brief"
    ) -> str:
        return f"# {metadata.title}\n\nmode={mode}\n\n{transcript.text}"


class RecordingWriter:
    """Captures what it was asked to write instead of touching the filesystem."""

    def __init__(self) -> None:
        self.markdown: str | None = None
        self.metadata: MediaMetadata | None = None

    def write(self, markdown: str, metadata: MediaMetadata) -> Path:
        self.markdown = markdown
        self.metadata = metadata
        return Path("output") / "fake.md"
