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

### 1. Prerequisites
- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — `brew install uv`
- **ffmpeg** (yt-dlp needs it to extract audio) — `brew install ffmpeg`
- **A free Groq API key** — create one at <https://console.groq.com/keys>
- **Claude Code, logged in on a Max/Pro subscription** — the summary runs on *your*
  subscription, so there's **no Anthropic API key** and no per-token bill. Install from
  <https://claude.com/claude-code>.

### 2. Install
```bash
uv venv
uv pip install -e ".[dev]"

cp .env.example .env        # then open .env and set GROQ_API_KEY=...

claude                      # run once and complete /login on your Max/Pro plan
```

### 3. Run
```bash
.venv/bin/parse "https://www.youtube.com/watch?v=…"
```
Writes a `.md` to `./output/` and prints its path.
Options: `-o <dir>` (output directory) · `-m opus|sonnet|haiku` (summary model, default `opus`).
