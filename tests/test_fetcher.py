"""Unit tests for the fetcher's pure helpers.

We can't (and shouldn't) hit the network in a unit test, so we exercise the two
tricky pieces of logic directly: metadata normalisation and locating the
post-processed audio file. The yt-dlp download itself is covered by manual
end-to-end runs.
"""

from __future__ import annotations

import pytest

from raw_media_parser.errors import FetchError
from raw_media_parser.fetcher import _metadata_from_info, _resolve_audio_path


def test_metadata_prefers_uploader_but_falls_back_to_channel() -> None:
    info = {
        "title": "Great Talk",
        "webpage_url": "https://youtube.com/watch?v=abc",
        "channel": "Some Channel",  # no `uploader` key
        "duration": 123.4,
        "upload_date": "20260101",
    }

    meta = _metadata_from_info(info, fallback_url="https://input.url")

    assert meta.title == "Great Talk"
    assert meta.url == "https://youtube.com/watch?v=abc"
    assert meta.uploader == "Some Channel"
    assert meta.duration == 123.4
    assert meta.upload_date == "20260101"


def test_metadata_uses_fallbacks_when_fields_missing() -> None:
    meta = _metadata_from_info({}, fallback_url="https://input.url")

    assert meta.title == "untitled"
    assert meta.url == "https://input.url"  # no webpage_url -> fall back to input
    assert meta.uploader is None


def test_resolve_audio_path_uses_requested_downloads(tmp_path) -> None:
    audio = tmp_path / "video123.mp3"
    audio.write_bytes(b"x")
    info = {"requested_downloads": [{"filepath": str(audio)}], "id": "video123"}

    assert _resolve_audio_path(info, tmp_path) == audio


def test_resolve_audio_path_falls_back_to_id_then_glob(tmp_path) -> None:
    audio = tmp_path / "vid.mp3"
    audio.write_bytes(b"x")

    # No requested_downloads: reconstruct from id
    assert _resolve_audio_path({"id": "vid"}, tmp_path) == audio
    # No id either: glob the dir
    assert _resolve_audio_path({}, tmp_path) == audio


def test_resolve_audio_path_raises_when_nothing_produced(tmp_path) -> None:
    with pytest.raises(FetchError):
        _resolve_audio_path({}, tmp_path)
