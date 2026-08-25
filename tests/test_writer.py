"""Unit tests for the Markdown writer (pure filesystem, no mocking needed)."""

from __future__ import annotations

from raw_media_parser.models import MediaMetadata
from raw_media_parser.writer import MarkdownWriter, slugify


def test_slugify_normalises_titles() -> None:
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  Multiple   Spaces ") == "multiple-spaces"
    assert slugify("Weird__chars--here") == "weird-chars-here"
    assert slugify("") == "untitled"
    assert slugify("!!!") == "untitled"


def test_slugify_truncates_to_max_length() -> None:
    assert len(slugify("a" * 200, max_length=10)) <= 10


def test_write_creates_file_named_after_title(tmp_path) -> None:
    writer = MarkdownWriter(tmp_path / "out")
    meta = MediaMetadata(title="My Great Talk", url="https://x")

    path = writer.write("# hi\n", meta)

    assert path == tmp_path / "out" / "my-great-talk.md"
    assert path.read_text(encoding="utf-8") == "# hi\n"


def test_write_never_overwrites(tmp_path) -> None:
    writer = MarkdownWriter(tmp_path)
    meta = MediaMetadata(title="Dup", url="https://x")

    first = writer.write("a", meta)
    second = writer.write("b", meta)

    assert first.name == "dup.md"
    assert second.name == "dup-2.md"
    assert first.read_text() == "a"
    assert second.read_text() == "b"
