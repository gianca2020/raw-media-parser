"""Audio fetching adapter: implements the `AudioFetcher` port with yt-dlp.

Responsibility: given a URL, download *audio only* into the directory the pipeline
hands it, convert it to a small speech-friendly file, and report what the source is.

Two design points worth calling out:

* We extract audio-only and downsample to **mono / 16 kHz mp3**. Speech-to-text does
  not benefit from stereo or high sample rates, and the smaller file stays under the
  ~25 MB limit hosted STT APIs impose and costs less to transcribe.
* The two fiddly, easy-to-get-wrong bits — mapping yt-dlp's `info` dict to our
  `MediaMetadata`, and finding the *post-processed* file path — are pulled out into
  pure module-level functions so they can be unit-tested without a network call.
"""

from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from .errors import FetchError
from .models import AudioArtifact, MediaMetadata

AUDIO_CODEC = "mp3"
DEFAULT_SAMPLE_RATE = 16_000  # 16 kHz mono is plenty for speech


def _metadata_from_info(info: dict, fallback_url: str) -> MediaMetadata:
    """Map yt-dlp's info dict onto our own metadata type.

    yt-dlp fields are inconsistent across sites (e.g. `uploader` vs `channel`), so we
    normalise here and keep the rest of the app insulated from those quirks.
    """
    return MediaMetadata(
        title=info.get("title") or "untitled",
        url=info.get("webpage_url") or fallback_url,
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        upload_date=info.get("upload_date"),  # "YYYYMMDD"
    )


def _resolve_audio_path(info: dict, dest_dir: Path) -> Path:
    """Find the file that survived post-processing (the extracted audio).

    After `FFmpegExtractAudio` runs, the original download (e.g. `.webm`) is replaced
    by an `.mp3`. yt-dlp records the final path under `requested_downloads`, but we
    fall back to reconstructing it (or globbing) for robustness across versions.
    """
    for download in info.get("requested_downloads") or []:
        filepath = download.get("filepath")
        if filepath:
            return Path(filepath)

    video_id = info.get("id")
    if video_id:
        candidate = dest_dir / f"{video_id}.{AUDIO_CODEC}"
        if candidate.exists():
            return candidate

    extracted = sorted(dest_dir.glob(f"*.{AUDIO_CODEC}"))
    if extracted:
        return extracted[0]

    raise FetchError("audio extraction produced no output file")


class YtDlpFetcher:
    """`AudioFetcher` backed by yt-dlp (handles YouTube, TikTok, Instagram, X, …)."""

    def __init__(self, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate

    def _options(self, dest_dir: Path) -> dict:
        return {
            "format": "bestaudio/best",
            "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
            "noplaylist": True,  # a URL that resolves to a playlist -> take the single video
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": AUDIO_CODEC,
                    "preferredquality": "64",
                }
            ],
            # Applied to ffmpeg: force mono + downsample. Smaller file, cheaper STT.
            "postprocessor_args": ["-ac", "1", "-ar", str(self._sample_rate)],
        }

    def fetch(self, url: str, dest_dir: Path) -> AudioArtifact:
        try:
            with YoutubeDL(self._options(dest_dir)) as ydl:
                info = ydl.extract_info(url, download=True)
        except DownloadError as exc:
            # Unsupported site, private/removed video, geo-block, network error, …
            raise FetchError(f"could not download audio for {url}: {exc}") from exc

        if info is None:
            raise FetchError(f"no media found at {url}")

        audio_path = _resolve_audio_path(info, dest_dir)
        metadata = _metadata_from_info(info, fallback_url=url)
        return AudioArtifact(path=audio_path, metadata=metadata)
