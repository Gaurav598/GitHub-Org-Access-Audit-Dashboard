"""Command line entry point for mock and authorized live reports."""
from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from importlib.resources import files
from .api import AuditAPIError, GitHubAPI
from .collector import collect
from .dashboard import render


def parser():
    p = argparse.ArgumentParser(description="Read-only GitHub organization access audit")
    sub = p.add_subparsers(dest="command", required=True)
    for mode in ("mock", "live"):
        s = sub.add_parser(mode)
        s.add_argument("--out", type=Path, default=Path("out"))
        if mode == "live":
            s.add_argument("--org", default=os.environ.get("GITHUB_ORG"))
            s.add_argument("--max-pages", type=int, default=5)
            s.add_argument("--window-days", type=int, default=90)
    s = sub.add_parser("serve", help="serve an existing report from loopback only")
    s.add_argument("--out", type=Path, default=Path("out"))
    s.add_argument("--port", type=int, default=8765)
    return p


def write_report(data, out):
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "dashboard.html").write_text(render(data), encoding="utf-8")
    (out / "audit.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return out / "dashboard.html"


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "serve":
            if not (args.out / "dashboard.html").is_file():
                raise ValueError("No dashboard found; run mock or live first")
            if not 1 <= args.port <= 65535:
                raise ValueError("port must be between 1 and 65535")
            directory = str(args.out.resolve())
            handler = lambda *a, **kw: SimpleHTTPRequestHandler(*a, directory=directory, **kw)
            with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
                print(f"Open http://127.0.0.1:{args.port}/dashboard.html", flush=True)
                server.serve_forever()
            return 0
        if args.command == "mock":
            data = json.loads(files("org_audit").joinpath("data/mock.json").read_text(encoding="utf-8"))
        else:
            if not args.org:
                raise ValueError("GITHUB_ORG or --org is required for live collection")
            token = os.environ.get("GITHUB_TOKEN")
            if not token:
                raise ValueError("GITHUB_TOKEN is required for live collection")
            data = collect(GitHubAPI(token), args.org, max_pages=args.max_pages, window_days=args.window_days)
        path = write_report(data, args.out)
        print(f"{data['mode'].upper()} report: {path}")
        return 0
    except (ValueError, AuditAPIError, OSError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
