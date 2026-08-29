"""Unit tests for the fetcher's pure helpers.

We can't (and shouldn't) hit the network in a unit test, so we exercise the two
tricky pieces of logic directly: metadata normalisation and locating the
post-processed audio file. The yt-dlp download itself is covered by manual
end-to-end runs.
"""

from __future__ import annotations

import pytest

from raw_media_parser.errors import FetchError
from raw_media_parser.fetcher import (
    _ensure_has_media,
    _metadata_from_info,
    _resolve_audio_path,
    _strip_upstream_noise,
)


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


# -- "there is no video here" reporting ------------------------------------
#
# yt-dlp's own message for a post with no video is actively misleading: it says
# "No video formats found! ... please report this issue on <yt-dlp issues>" and
# "Confirm you are on the latest version". Both send the user chasing a bug that
# does not exist -- the real answer is that the post is a photo. These tests pin
# the accurate message. The carousel shape below is the real structure returned
# for instagram.com/p/DZMAemcia7Y/ (7 image entries, zero formats each).


def test_carousel_of_images_is_reported_as_having_no_video() -> None:
    info = {
        "_type": "playlist",
        "id": "DZMAemcia7Y",
        "title": "Post by techwith.ram",
        "entries": [
            {"id": f"child{n}", "formats": [], "vcodec": None, "duration": None}
            for n in range(7)
        ],
    }

    with pytest.raises(FetchError) as exc:
        _ensure_has_media(info, "https://www.instagram.com/p/DZMAemcia7Y/")

    message = str(exc.value)
    assert "no video" in message.lower()
    assert "7" in message  # tell the user what it actually is
    assert "yt-dlp" not in message.lower()  # never relay "report this upstream"


def test_single_item_without_formats_is_reported_as_having_no_video() -> None:
    with pytest.raises(FetchError) as exc:
        _ensure_has_media({"id": "x", "formats": []}, "https://example.com/photo")

    assert "no video" in str(exc.value).lower()


def test_playlist_with_a_video_entry_is_allowed_through() -> None:
    info = {
        "_type": "playlist",
        "entries": [
            {"id": "a", "formats": []},
            {"id": "b", "formats": [{"format_id": "mp4"}]},  # one real video
        ],
    }

    _ensure_has_media(info, "https://example.com/mixed")  # must not raise


def test_normal_video_is_allowed_through() -> None:
    _ensure_has_media({"id": "v", "formats": [{"format_id": "mp4"}]}, "https://e.com/v")


def test_empty_playlist_is_reported_as_no_media() -> None:
    with pytest.raises(FetchError) as exc:
        _ensure_has_media({"_type": "playlist", "entries": []}, "https://e.com/empty")

    assert "no media" in str(exc.value).lower()


# -- yt-dlp boilerplate stripping ------------------------------------------


def test_upstream_boilerplate_is_stripped_from_relayed_errors() -> None:
    raw = (
        "ERROR: [Instagram] DZMAeXZCYpY: No video formats found!; please report "
        "this issue on  https://github.com/yt-dlp/yt-dlp/issues?q= , filling out "
        "the appropriate issue template. Confirm you are on the latest version "
        "using  yt-dlp -U"
    )

    cleaned = _strip_upstream_noise(raw)

    assert "please report this issue" not in cleaned
    assert "yt-dlp -U" not in cleaned
    assert "No video formats found" in cleaned  # keep the substantive part
