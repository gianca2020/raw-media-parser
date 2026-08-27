"""Application settings, read from the environment.

Kept deliberately dumb: it only reads `os.environ` and validates that the two
required keys are present. It imports no adapters and does no I/O beyond env
lookups, so it is trivial to construct in tests. Loading a `.env` file is the
CLI's job (the composition root), not this module's.
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
    anthropic_api_key: str
    groq_api_key: str
    model: str = DEFAULT_MODEL
    effort: str = DEFAULT_EFFORT
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)

    @classmethod
    def from_env(cls) -> "Settings":
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        groq_key = os.environ.get("GROQ_API_KEY", "").strip()

        missing = [
            name
            for name, value in (
                ("ANTHROPIC_API_KEY", anthropic_key),
                ("GROQ_API_KEY", groq_key),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill them in."
            )

        return cls(
            anthropic_api_key=anthropic_key,
            groq_api_key=groq_key,
            model=os.environ.get("RMP_MODEL", DEFAULT_MODEL),
            effort=os.environ.get("RMP_EFFORT", DEFAULT_EFFORT),
            output_dir=Path(os.environ.get("RMP_OUTPUT_DIR", DEFAULT_OUTPUT_DIR)),
        )
