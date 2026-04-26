#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "external" / "policy-fabric" / "prophet_operations_action_decision_v1.schema.json"
DEFAULT_PATH = "/v1/operations/action-decision"


class PolicyFabricClientError(Exception):
    pass


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PolicyFabricClientError(f"expected JSON object in {path}")
    return data


def endpoint_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base + DEFAULT_PATH


def request_decision(*, base_url: str, recommendation: dict[str, Any], mode: str, timeout_seconds: float = 5.0) -> dict[str, Any]:
    payload = json.dumps({"recommendation": recommendation, "mode": mode}, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(
        endpoint_url(base_url),
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310 - explicit operator-supplied endpoint
            body = resp.read().decode("utf-8")
            if resp.status < 200 or resp.status >= 300:
                raise PolicyFabricClientError(f"Policy Fabric endpoint returned HTTP {resp.status}: {body}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PolicyFabricClientError(f"Policy Fabric endpoint returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise PolicyFabricClientError(f"Policy Fabric endpoint unavailable: {exc.reason}") from exc

    data = json.loads(body)
    if not isinstance(data, dict):
        raise PolicyFabricClientError("Policy Fabric endpoint returned non-object JSON")
    schema = load_json(SCHEMA)
    jsonschema.validate(data, schema)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Request a Prophet operations action decision from a live Policy Fabric endpoint")
    parser.add_argument("--endpoint", required=True, help="Policy Fabric base URL, e.g. http://127.0.0.1:8080")
    parser.add_argument("--recommendation", type=Path, required=True, help="Operations recommendation JSON object")
    parser.add_argument("--mode", default="report_only", choices=["report_only", "enforcing"])
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    decision = request_decision(
        base_url=args.endpoint,
        recommendation=load_json(args.recommendation),
        mode=args.mode,
        timeout_seconds=args.timeout_seconds,
    )
    encoded = json.dumps(decision, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
