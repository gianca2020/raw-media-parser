"""Domain exceptions.

Each pipeline stage raises its own subclass so the CLI can report exactly which
step failed without leaking library-specific exception types.
"""

from __future__ import annotations


class ParserError(Exception):
    """Base class for all raw-media-parser errors."""


class ConfigError(ParserError):
    """Missing or invalid configuration (e.g. an unset API key)."""


class FetchError(ParserError):
    """Could not download audio for the given URL."""


class TranscriptionError(ParserError):
    """The speech-to-text stage failed."""


class SummarizationError(ParserError):
    """The summarization stage failed."""
