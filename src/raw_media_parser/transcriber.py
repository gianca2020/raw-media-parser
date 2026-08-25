"""Transcription adapter: implements the `Transcriber` port with Groq Whisper.

Responsibility: audio file in, spoken text out. This is the one stage that *must*
live outside Claude — the Anthropic API has no audio input, so speech-to-text needs a
dedicated provider. Groq's hosted `whisper-large-v3-turbo` is the default (fast + cheap);
swapping to OpenAI/Deepgram later means a new class implementing this same port and one
line in the CLI — nothing else changes.

The Groq client is injectable (`client=`) so the whole adapter can be unit-tested with a
fake, no API key or network required.
"""

from __future__ import annotations

from pathlib import Path

from groq import Groq

from .errors import TranscriptionError
from .models import Transcript

DEFAULT_MODEL = "whisper-large-v3-turbo"


class GroqTranscriber:
    """`Transcriber` backed by Groq's hosted Whisper endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = DEFAULT_MODEL,
        client: object | None = None,
    ) -> None:
        self._client = client if client is not None else Groq(api_key=api_key)
        self._model = model

    def transcribe(self, audio_path: Path) -> Transcript:
        path = Path(audio_path)
        try:
            with path.open("rb") as audio_file:
                response = self._client.audio.transcriptions.create(
                    file=(path.name, audio_file.read()),
                    model=self._model,
                )
        except Exception as exc:  # translate any SDK/IO/network failure at the boundary
            raise TranscriptionError(
                f"transcription failed for {path.name}: {exc}"
            ) from exc

        text = _extract_text(response)
        if not text:
            raise TranscriptionError("transcription returned no text")
        return Transcript(text=text)


def _extract_text(response: object) -> str:
    """Pull the transcript string out of the SDK response, tolerant of shape."""
    text = getattr(response, "text", None)
    if text is None and isinstance(response, dict):
        text = response.get("text")
    return (text or "").strip()
