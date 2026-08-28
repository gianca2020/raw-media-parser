# raw-media-parser

## What it is

Turn a video **URL** into a concise **Markdown brief** of what's said in it.

Pass a link (YouTube, TikTok, Instagram, X) and it downloads the audio, transcribes it,
and summarizes the key information with Claude into a `.md` file:

```
URL ─▶ download audio (yt-dlp) ─▶ transcribe (Groq) ─▶ summarize (Claude) ─▶ output/<title>.md
```

Claude has no audio input, so transcription uses Groq; Claude only handles the text summary.

## Setup

Each person sets this up on their own machine — no secrets are shared or committed.

> **Command convention.** Every command below uses `python3`. On **Windows**, use
> `py` instead — `py -m pip …`, `py parse.py …`, `py -m pytest`. Nothing else changes.
> Invoking pip as `python3 -m pip` (rather than `pip3`) guarantees you install into
> the *same* interpreter you will run the app with, on every platform.

### 1. Prerequisites

| Need | Check | Install |
|---|---|---|
| **Python 3.11+** | `python3 --version` | Present on most Linux/macOS. Windows: <https://python.org/downloads> (tick *Add python.exe to PATH*) |
| **ffmpeg** — yt-dlp uses it to extract audio | `ffmpeg -version` | macOS `brew install ffmpeg` · Debian/Ubuntu `sudo apt install ffmpeg` · Fedora `sudo dnf install ffmpeg` · Arch `sudo pacman -S ffmpeg` · Windows `winget install Gyan.FFmpeg` |
| **Groq API key** — free | — | <https://console.groq.com/keys> |
| **Claude Code**, logged in on a Max/Pro plan | `claude --version` | <https://claude.com/claude-code> — the summary runs on *your* subscription, so there is **no Anthropic API key** and no per-token bill |

### 2. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

<b>If that fails with <code>error: externally-managed-environment</code></b> — common on
Homebrew Python, Debian/Ubuntu, Fedora, and other distro-managed interpreters, which
refuse installs into themselves (PEP 668) to protect OS tooling — pick one:

```bash
# A. Install into your personal package dir, overriding the guard
python3 -m pip install --user --break-system-packages -r requirements.txt

# B. Or isolate, if you would rather not touch the system interpreter
python3 -m venv .venv
python3 -m pip install -r requirements.txt   # after activating, see below
```

For **B**, activate first: `source .venv/bin/activate` (macOS/Linux) or
`.venv\Scripts\activate` (Windows).

**A** is simpler and is what this project assumes; the trade is that your Python
packages are shared across projects, so a version conflict with another project
becomes possible. **B** avoids that at the cost of activating the environment each
session. Either works — the app itself does not care.

### 3. Configure

```bash
cp .env.example .env          # Windows: copy .env.example .env
```

Open `.env` and set `GROQ_API_KEY=…`. Then run `claude` once and complete `/login`.

There is no build step and nothing to install for the app itself — `parse.py` puts
`src/` on the import path, so a clone plus the dependencies above is enough.

### 4. Run

```bash
python3 parse.py "https://www.youtube.com/watch?v=…"
```

Writes a `.md` to `./output/` and prints its path.
Options: `-o <dir>` (output directory) · `-m opus|sonnet|haiku` (summary model, default `opus`).

Exit codes: `0` success · `1` a stage failed · `2` misconfiguration. Progress goes to
stderr and the path alone to stdout, so it composes: `open "$(python3 parse.py <url>)"`.

### 5. Tests

```bash
python3 -m pip install -r requirements-dev.txt   # same fallback as step 2 if needed
python3 -m pytest
```

Run pytest as `python3 -m pytest`, not bare `pytest`. A `--user` install puts console
scripts in a directory that is often not on `PATH` — `python3 -m site --user-base`
prints where, if you want to add it.

The suite uses in-memory fakes — no keys, no network, no ffmpeg.
