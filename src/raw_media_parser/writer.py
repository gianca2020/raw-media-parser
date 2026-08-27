"""Output adapter: implements the `MarkdownWriter` port to the local filesystem.

Responsibility: take the finished Markdown and metadata, and write a `.md` file named
after the video, without ever clobbering an existing summary.

`slugify` is a plain function (easy to test and reuse); the writer handles the
directory-creation and name-collision policy.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import MediaMetadata

SLUG_MAX_LENGTH = 80


def slugify(text: str, *, max_length: int = SLUG_MAX_LENGTH) -> str:
    """Turn a title into a safe, readable filename stem (e.g. 'my-great-talk')."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)  # drop punctuation
    text = re.sub(r"[\s_-]+", "-", text).strip("-")  # collapse runs to single dashes
    text = text[:max_length].strip("-")
    return text or "untitled"


class MarkdownWriter:
    """`MarkdownWriter` that writes to a configurable output directory."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)

    def write(self, markdown: str, metadata: MediaMetadata) -> Path:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        base = slugify(metadata.title)
        path = self._output_dir / f"{base}.md"

        # Never overwrite an existing summary: my-talk.md, my-talk-2.md, my-talk-3.md, …
        counter = 2
        while path.exists():
            path = self._output_dir / f"{base}-{counter}.md"
            counter += 1

        path.write_text(markdown, encoding="utf-8")
        return path
