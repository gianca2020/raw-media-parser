"""Application settings, read from the environment.

Kept deliberately dumb: it only reads `os.environ` and validates that the required
`GROQ_API_KEY` is present. It imports no adapters and does no I/O beyond env lookups,
so it is trivial to construct in tests. Loading a `.env` file is the CLI's job (the
composition root), not this module's.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_EFFORT = "medium"  # summarization isn't intelligence-critical; keep it cheap/fast
DEFAULT_OUTPUT_DIR = "output"


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    # Optional: only used if you wire up the API-based `ClaudeSummarizer`. The default
    # summarizer runs through the Claude Code CLI on your subscription, so no key needed.
    anthropic_api_key: str = ""
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)

    @classmethod
    def from_env(cls) -> "Settings":
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not groq_key:
            raise ConfigError(
                "Missing required environment variable: GROQ_API_KEY. "
                "Copy .env.example to .env and fill it in."
            )

        return cls(
            groq_api_key=groq_key,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "").strip(),
            model=os.environ.get("RMP_MODEL", DEFAULT_MODEL),
            effort=os.environ.get("RMP_EFFORT", DEFAULT_EFFORT),
            output_dir=Path(os.environ.get("RMP_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
        )
