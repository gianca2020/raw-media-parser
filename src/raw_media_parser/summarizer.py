"""Summarization adapter: implements the `Summarizer` port with Claude.

Responsibility: transcript (+ metadata) -> a Markdown brief.

Key design choice — **split deterministic facts from model-written analysis**:

* The metadata header (title, channel, source URL, duration, date) is formatted in
  code. Those are known facts; asking the model to echo them only risks hallucination
  and wastes tokens.
* Claude writes only the *analytical* body (TL;DR, key points, takeaways, actions).

The Anthropic client is injectable (`client=`) so the adapter is unit-testable with a
fake — no key, no network, no tokens.
"""

from __future__ import annotations

from anthropic import Anthropic

from .errors import SummarizationError
from .models import MediaMetadata, Transcript
from .prompts import SYSTEM_PROMPT, build_user_content

# Roomy enough for adaptive thinking plus a one-page brief, still well under the
# threshold where non-streaming requests risk an HTTP timeout.
MAX_TOKENS = 8_000


class ClaudeSummarizer:
    """`Summarizer` backed by the Anthropic Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str,
        effort: str = "medium",
        client: object | None = None,
    ) -> None:
        self._client = client if client is not None else Anthropic(api_key=api_key)
        self._model = model
        self._effort = effort

    def summarize(
        self, transcript: Transcript, metadata: MediaMetadata, mode: str = "brief"
    ) -> str:
        # `mode` is the reserved seam for a future "detailed" option; only the brief
        # template exists today.
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={"effort": self._effort},
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": build_user_content(
                            transcript.text,
                            title=metadata.title,
                            uploader=metadata.uploader,
                        ),
                    }
                ],
            )
        except Exception as exc:  # translate any SDK/network failure at the boundary
            raise SummarizationError(f"summarization failed: {exc}") from exc

        body = _extract_text(response)
        if not body:
            raise SummarizationError("summarizer returned no text")
        return f"{_build_header(metadata)}\n{body}\n"


def _extract_text(response: object) -> str:
    """Concatenate the text blocks of a Messages response, ignoring thinking blocks."""
    parts = [
        getattr(block, "text", "")
        for block in (getattr(response, "content", None) or [])
        if getattr(block, "type", None) == "text"
    ]
    return "".join(parts).strip()


def _build_header(metadata: MediaMetadata) -> str:
    """Format the deterministic metadata header from known facts."""
    facts = []
    if metadata.uploader:
        facts.append(f"**Channel:** {metadata.uploader}")
    facts.append(f"**Source:** {metadata.url}")
    duration = _format_duration(metadata.duration)
    if duration:
        facts.append(f"**Duration:** {duration}")
    date = _format_date(metadata.upload_date)
    if date:
        facts.append(f"**Uploaded:** {date}")

    facts_block = "  \n".join(facts)  # two trailing spaces = Markdown hard line break
    return f"# {metadata.title}\n\n{facts_block}\n"


def _format_duration(seconds: float | int | None) -> str | None:
    """Seconds -> `m:ss` or `h:mm:ss`; None/0 -> None."""
    if not seconds:
        return None
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_date(yyyymmdd: str | None) -> str | None:
    """yt-dlp's `YYYYMMDD` -> `YYYY-MM-DD`; pass through anything unexpected."""
    if not yyyymmdd:
        return None
    if len(yyyymmdd) == 8 and yyyymmdd.isdigit():
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return yyyymmdd
