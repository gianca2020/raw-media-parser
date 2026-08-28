#!/usr/bin/env python3
"""Launch the local web UI: `python3 serve.py` then open http://127.0.0.1:8000

The CLI (`parse.py`) and this server are two surfaces over the same `Pipeline`;
neither owns any parsing logic. This file is the web surface's composition root,
mirroring what `cli.py` does for the command line.

Local and private by design — it binds to loopback only. See the note in
`raw_media_parser/web/server.py` for why exposing it would be a mistake.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import argparse  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

from raw_media_parser.cli_summarizer import ClaudeCliSummarizer  # noqa: E402
from raw_media_parser.config import Settings  # noqa: E402
from raw_media_parser.errors import ParserError  # noqa: E402
from raw_media_parser.fetcher import YtDlpFetcher  # noqa: E402
from raw_media_parser.pipeline import Pipeline  # noqa: E402
from raw_media_parser.transcriber import GroqTranscriber  # noqa: E402
from raw_media_parser.web.server import serve  # noqa: E402
from raw_media_parser.writer import MarkdownWriter  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1",
                    help="loopback by default; changing this exposes your "
                         "Claude subscription to anyone who can reach the port")
    ap.add_argument("-o", "--output-dir", type=Path, default=None)
    ap.add_argument("-m", "--model", default="opus", help="opus | sonnet | haiku")
    args = ap.parse_args()

    load_dotenv()
    try:
        settings = Settings.from_env()
    except ParserError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    pipeline = Pipeline(
        fetcher=YtDlpFetcher(),
        transcriber=GroqTranscriber(settings.groq_api_key),
        summarizer=ClaudeCliSummarizer(model=args.model),
        writer=MarkdownWriter(args.output_dir or settings.output_dir),
    )

    httpd = serve(pipeline, host=args.host, port=args.port)
    print(f"raw-media-parser → http://{args.host}:{args.port}  (ctrl-c to stop)",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
