"""Tests for the CLI composition root.

We don't hit the network: we patch out `load_dotenv` (so a developer's real `.env`
can't leak into the test) and swap the `Pipeline` for a fake. That leaves the CLI's
own responsibilities under test — config validation, wiring, and exit-code mapping.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from raw_media_parser import cli as cli_module

runner = CliRunner()


def test_missing_keys_exits_with_code_2(monkeypatch) -> None:
    monkeypatch.setattr(cli_module, "load_dotenv", lambda *a, **k: None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = runner.invoke(cli_module.app, ["https://example.com/video"])

    assert result.exit_code == 2
    assert "Config error" in result.output


def test_success_prints_output_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cli_module, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    out_file = tmp_path / "out.md"

    class FakePipeline:
        def __init__(self, **kwargs):
            pass

        def run(self, url, mode="brief"):
            return out_file

    monkeypatch.setattr(cli_module, "Pipeline", FakePipeline)

    result = runner.invoke(
        cli_module.app, ["https://example.com/video", "-o", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert str(out_file) in result.output
