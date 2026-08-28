#!/usr/bin/env python3
"""Executable entry point: `./parse.py <url>` or `python3 parse.py <url>`.

The application code lives under `src/`, which keeps the importable package
separate from repo scaffolding (tests, config, this launcher). That layout
normally requires the package to be *installed* before Python can find it; this
launcher removes that step by putting `src/` on the import path itself, so the
only setup anyone needs is `pip install -r requirements.txt`.

The real CLI — arguments, options, exit codes — is defined in
`raw_media_parser.cli`. This file deliberately contains no application logic.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from raw_media_parser.cli import app  # noqa: E402  (import follows the path setup)

if __name__ == "__main__":
    app()
