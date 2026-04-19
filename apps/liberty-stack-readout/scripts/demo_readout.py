#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} /path/to/receipt.json", file=sys.stderr)
        return 2

    receipt_path = sys.argv[1]
    url = "http://127.0.0.1:8080/v1/liberty-stack/readout?" + urllib.parse.urlencode({"receipt": receipt_path})
    with urllib.request.urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
