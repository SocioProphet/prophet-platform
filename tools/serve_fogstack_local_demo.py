#!/usr/bin/env python3
from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
from pathlib import Path


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve generated FogStack local demo artifacts")
    parser.add_argument("--directory", type=Path, default=Path("build/fogstack-local-demo"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    directory = args.directory.resolve()
    index = directory / "index.html"
    if not directory.exists() or not directory.is_dir():
        print(f"ERR: demo directory does not exist: {directory}", file=sys.stderr)
        return 1
    if not index.exists() or not index.is_file():
        print(f"ERR: demo index.html does not exist: {index}", file=sys.stderr)
        return 1

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    with ReusableTCPServer((args.host, args.port), handler) as httpd:
        host, port = httpd.server_address
        print(f"Serving FogStack local demo at http://{host}:{port}/index.html", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
