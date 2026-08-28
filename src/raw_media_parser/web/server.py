"""A local, private web surface for the pipeline.

Deliberately built on the Python standard library (`http.server`) rather than a
framework: three endpoints do not justify a new dependency, and this project's
setup story is already the interesting part of its README.

**This server is local-only by design.** It binds to loopback and is never
exposed. That is not merely a default — the summarizer shells out to
`claude --print` against *this machine's* Claude Code subscription login, so a
publicly reachable instance would spend the host's subscription on every
visitor's request. Hosting this for real means swapping in the API-key-based
`ClaudeSummarizer` at the composition root.

Shape:

    POST /api/parse        {"url": …}  -> {"job_id": …}   (starts a worker thread)
    GET  /api/status/<id>              -> stage, or the finished result
    GET  /                             -> the single page

A run takes minutes, so the work happens on a background thread and the page
polls for its stage. Jobs live in memory only; this is a single-user tool.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from ..errors import ParserError
from ..pipeline import Pipeline

_PAGE = Path(__file__).with_name("index.html")

# yt-dlp accepts more than http(s); a web form should not reach schemes like
# file:// that would let a page request read off the host.
_ALLOWED_SCHEMES = ("http", "https")


@dataclass
class Job:
    """One parse run's observable state."""

    id: str
    url: str
    status: str = "running"          # running | done | error
    stage: Optional[str] = None      # fetch | transcribe | summarize | write
    result: Optional[dict] = None
    error: Optional[str] = None
    failed_stage: Optional[str] = None

    def snapshot(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "stage": self.stage,
            "result": self.result,
            "error": self.error,
            "failed_stage": self.failed_stage,
        }


class JobRegistry:
    """In-memory job store. Threads write, request handlers read."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, url: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], url=url)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)


def run_job(job: Job, pipeline: Pipeline) -> None:
    """Execute one pipeline run, recording progress and outcome on `job`.

    Exposed (rather than nested in the thread target) so tests can drive a whole
    run synchronously with the in-memory fakes.
    """
    try:
        result = pipeline.run(job.url, on_stage=lambda s: setattr(job, "stage", s))
    except ParserError as exc:
        job.status = "error"
        job.failed_stage = job.stage
        job.error = f"{type(exc).__name__}: {exc}"
        return
    except Exception as exc:  # never let a worker thread die silently
        job.status = "error"
        job.failed_stage = job.stage
        job.error = f"Unexpected error: {exc}"
        return

    job.result = {
        "markdown": result.markdown,
        "transcript": result.transcript.text,
        "path": str(result.path),
        "title": result.metadata.title,
        "uploader": result.metadata.uploader,
        "duration": result.metadata.duration,
        "url": result.metadata.url,
    }
    job.stage = None
    job.status = "done"


def make_handler(pipeline: Pipeline, registry: JobRegistry):
    """Build a request handler bound to one pipeline and job registry."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "raw-media-parser"

        # -- helpers ---------------------------------------------------------
        def _json(self, payload: dict, code: int = 200) -> None:
            body = json.dumps(payload).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # quieter than the default access log
            pass

        # -- routes ----------------------------------------------------------
        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                body = _PAGE.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path.startswith("/api/status/"):
                job = registry.get(self.path.rsplit("/", 1)[-1])
                if job is None:
                    self._json({"error": "unknown job"}, 404)
                    return
                self._json(job.snapshot())
                return

            self._json({"error": "not found"}, 404)

        def do_POST(self) -> None:
            if self.path != "/api/parse":
                self._json({"error": "not found"}, 404)
                return

            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._json({"error": "malformed JSON"}, 400)
                return

            url = (payload.get("url") or "").strip()
            if not url:
                self._json({"error": "a URL is required"}, 400)
                return
            if urlparse(url).scheme not in _ALLOWED_SCHEMES:
                self._json({"error": "URL must start with http:// or https://"}, 400)
                return

            job = registry.create(url)
            threading.Thread(
                target=run_job, args=(job, pipeline), daemon=True
            ).start()
            self._json({"job_id": job.id}, 202)

    return Handler


def serve(pipeline: Pipeline, host: str = "127.0.0.1", port: int = 8000):
    """Return a server bound to loopback. Caller runs it."""
    return ThreadingHTTPServer((host, port), make_handler(pipeline, JobRegistry()))
