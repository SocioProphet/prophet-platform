#!/usr/bin/env python3
"""Build the bundled academy seed from a captured OCW course JSONL (Knowledge Commons).

Reads the raw per-course chunk file (text/slug/field/material/source), drops boilerplate
(nav chrome, glyph garbage, stubs), dedups, cleans whitespace, derives a legible title, and
emits LearningSearchRecord JSONL for the search-orchestrator academy ingest.

Usage:
    python tools/build_academy_seed.py 8-01sc.jsonl app/seeds/academy-8.01.jsonl \
        --title "8.01 Classical Mechanics" --ref-prefix ocw://8.01SC
Source: gs://sourceos-artifacts-socioprophet/knowledge-commons/courseware/mit/courses/<slug>.jsonl
"""
from __future__ import annotations

import argparse
import json
import re

_NAV = re.compile(r"previous \| next|does not support|download (video|transcript)|view video page|watch it offline", re.I)
_WS = re.compile(r"\s+")


def clean(text: str) -> str:
    return _WS.sub(" ", text or "").strip()


def substantive(text: str) -> bool:
    c = clean(text)
    if len(c) < 160 or _NAV.search(c):
        return False
    words = c.split()
    if len(words) < 25:
        return False
    letters = sum(ch.isalpha() for ch in c)
    return letters >= 0.6 * len(c)  # drop glyph / symbol garbage (bad PDF extraction)


def title_of(text: str, fallback: str) -> str:
    c = clean(text)
    sentence = re.split(r"(?<=[.!?])\s", c)[0]
    t = sentence[:64].rstrip()
    return f"{fallback} — {t}…" if len(t) >= 24 else fallback


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dest")
    ap.add_argument("--title", default="OCW course")
    ap.add_argument("--ref-prefix", default="ocw://course")
    ap.add_argument("--max-chars", type=int, default=1000)
    args = ap.parse_args()

    seen: set[str] = set()
    out: list[str] = []
    for line in open(args.src, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        text = clean(rec.get("text", ""))
        if not substantive(text):
            continue
        key = text[:200].lower()
        if key in seen:
            continue
        seen.add(key)
        slug = rec.get("slug", f"chunk-{len(out)}")
        body = text[: args.max_chars]
        record = {
            "header": {
                "object_id": f"lsr_{slug}",
                "object_type": "LearningSearchRecord",
                "status": "published",
                "policy_tags": ["public", "cc-by-nc-sa-4.0", "ocw"],
            },
            "source": "ALEXANDRIAN_ACADEMY",
            "entity_type": "LEARNING_ACTION_EXPLANATION",
            "title": title_of(text, args.title),
            "text": body,
            "target_ref": f"{args.ref_prefix}/{slug}",
            "final_score": round(min(0.99, 0.7 + len(body) / 4000), 3),
        }
        out.append(json.dumps(record, ensure_ascii=False))

    with open(args.dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"wrote {len(out)} records to {args.dest}")


if __name__ == "__main__":
    main()
