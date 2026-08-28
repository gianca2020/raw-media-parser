"""Tests for the local web surface.

Same payoff as the pipeline tests: because the server only ever sees a
`Pipeline` built from the in-memory fakes, the whole request/response cycle is
exercised with no network, no API keys, and no ffmpeg. A real HTTP server is
started on an ephemeral port so the routing and JSON contract are tested for
real rather than by calling handler methods directly.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest
from conftest import FakeFetcher, FakeSummarizer, FakeTranscriber, RecordingWriter

from raw_media_parser.errors import FetchError
from raw_media_parser.models import MediaMetadata
from raw_media_parser.pipeline import Pipeline
from raw_media_parser.web.server import Job, JobRegistry, run_job, serve


def _meta() -> MediaMetadata:
    return MediaMetadata(title="Test Video", url="https://example.com/watch")


def _pipeline(transcript: str = "the spoken words") -> Pipeline:
    return Pipeline(
        FakeFetcher(_meta()), FakeTranscriber(transcript),
        FakeSummarizer(), RecordingWriter(),
    )


@pytest.fixture
def server():
    httpd = serve(_pipeline(), host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _post(base: str, payload: dict):
    req = urllib.request.Request(
        f"{base}/api/parse", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return urllib.request.urlopen(req)


# -- the job worker, driven synchronously ---------------------------------


def test_run_job_records_result_including_transcript() -> None:
    job = Job(id="x", url="https://example.com/watch")
    run_job(job, _pipeline("hello there"))

    assert job.status == "done"
    assert job.result is not None
    assert job.result["transcript"] == "hello there"
    assert "Test Video" in job.result["markdown"]
    assert job.result["title"] == "Test Video"


def test_run_job_records_which_stage_failed() -> None:
    class BoomFetcher:
        def fetch(self, url, dest_dir):
            raise FetchError("could not download")

    job = Job(id="x", url="https://example.com/watch")
    run_job(job, Pipeline(BoomFetcher(), FakeTranscriber(),
                          FakeSummarizer(), RecordingWriter()))

    assert job.status == "error"
    assert job.failed_stage == "fetch"
    assert "could not download" in job.error


# -- HTTP contract ---------------------------------------------------------


def test_get_root_serves_the_page(server) -> None:
    body = urllib.request.urlopen(server + "/").read().decode()
    assert "<title>raw-media-parser</title>" in body


def test_post_then_poll_returns_the_result(server) -> None:
    res = _post(server, {"url": "https://example.com/watch"})
    assert res.status == 202
    job_id = json.load(res)["job_id"]

    for _ in range(100):  # the fakes finish almost immediately
        job = json.load(urllib.request.urlopen(f"{server}/api/status/{job_id}"))
        if job["status"] != "running":
            break
    assert job["status"] == "done"
    assert job["result"]["transcript"] == "the spoken words"


def test_rejects_non_http_scheme(server) -> None:
    """A web form must not be able to reach file:// on the host."""
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, {"url": "file:///etc/passwd"})
    assert exc.value.code == 400


def test_rejects_empty_url(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(server, {"url": "  "})
    assert exc.value.code == 400


def test_unknown_job_is_404(server) -> None:
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{server}/api/status/nope")
    assert exc.value.code == 404


def test_registry_assigns_distinct_ids() -> None:
    reg = JobRegistry()
    a, b = reg.create("https://a"), reg.create("https://b")
    assert a.id != b.id
    assert reg.get(a.id).url == "https://a"
