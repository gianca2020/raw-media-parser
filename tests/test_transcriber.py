"""Unit tests for the Groq transcriber, using an injected fake client.

Because the client is injectable, we test the adapter's real logic — request shape,
text extraction, error translation, empty-result handling — with no key or network.
"""

from __future__ import annotations

import types

import pytest

from raw_media_parser.errors import TranscriptionError
from raw_media_parser.transcriber import GroqTranscriber, _extract_text


class _FakeTranscriptions:
    def __init__(self, *, text=None, raises=None):
        self._text = text
        self._raises = raises
        self.called_with: dict | None = None

    def create(self, *, file, model):
        self.called_with = {"file": file, "model": model}
        if self._raises is not None:
            raise self._raises
        return types.SimpleNamespace(text=self._text)


def _fake_client(*, text=None, raises=None):
    return types.SimpleNamespace(
        audio=types.SimpleNamespace(
            transcriptions=_FakeTranscriptions(text=text, raises=raises)
        )
    )


def _audio_file(tmp_path):
    path = tmp_path / "clip.mp3"
    path.write_bytes(b"bytes")
    return path


def test_transcribe_returns_stripped_text_and_sends_expected_request(tmp_path) -> None:
    client = _fake_client(text="  hello world  ")
    transcriber = GroqTranscriber(client=client, model="whisper-x")

    result = transcriber.transcribe(_audio_file(tmp_path))

    assert result.text == "hello world"
    sent = client.audio.transcriptions.called_with
    assert sent["model"] == "whisper-x"
    name, data = sent["file"]
    assert name == "clip.mp3"
    assert data == b"bytes"


def test_transcribe_wraps_client_errors(tmp_path) -> None:
    client = _fake_client(raises=RuntimeError("boom"))
    with pytest.raises(TranscriptionError):
        GroqTranscriber(client=client).transcribe(_audio_file(tmp_path))


def test_transcribe_raises_on_empty_text(tmp_path) -> None:
    client = _fake_client(text="   ")
    with pytest.raises(TranscriptionError):
        GroqTranscriber(client=client).transcribe(_audio_file(tmp_path))


def test_extract_text_tolerates_dict_response() -> None:
    assert _extract_text({"text": "  hi  "}) == "hi"
