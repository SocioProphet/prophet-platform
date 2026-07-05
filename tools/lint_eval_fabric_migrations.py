#!/usr/bin/env python3
"""Static consistency lint for the eval-fabric SQL migrations — no database required.

Guards the class of bug that shipped in the metric_crosswalks gap: 005 inserted into a
`metric_crosswalks` table whose `CREATE TABLE` existed nowhere, so a fresh
`eval_fabric_migrate` failed at 005. This lint reads the numbered migrations IN ORDER and
asserts, purely statically:

  1. every `INSERT INTO <t>` targets a table `CREATE`d by an earlier (or same, earlier-in-file)
     statement — no insert-before-create;
  2. every column named in an `INSERT ... (cols)` list exists in that table's `CREATE TABLE`.

It is intentionally scoped to the Postgres migrations (where the FK-less, text-id join model
makes a missing table load-but-not-join, i.e. silent). ClickHouse DDL (ENGINE=..., different
column grammar) is a follow-up. Stdlib-only; runnable in CI with no DB:

    python3 tools/lint_eval_fabric_migrations.py           # lints infra/datastores/postgres
    python3 tools/lint_eval_fabric_migrations.py --dir X    # lint another dir
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PG_DIR = ROOT / "infra" / "datastores" / "postgres"

# A part of a CREATE-TABLE body whose first token is one of these is a table-level constraint,
# not a column (an inline-constrained column still starts with its own name, so it is kept).
_CONSTRAINT_HEADS = {"primary", "foreign", "unique", "check", "constraint", "exclude"}
# A leading identifier, optionally double-quoted (reserved words like "window" are quoted).
_IDENT = re.compile(r'"?([a-zA-Z_][a-zA-Z0-9_]*)"?')


def _strip_comments(sql: str) -> str:
    return "\n".join(re.sub(r"--.*$", "", line) for line in sql.splitlines())


def _statements(sql: str) -> list[str]:
    return [s.strip() for s in _strip_comments(sql).split(";") if s.strip()]


def _balanced(text: str, open_idx: int) -> str | None:
    """Return the content between the '(' at `open_idx` and its matching ')', or None."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1 : i]
    return None


def _split_top_level(body: str) -> list[str]:
    """Split on commas that are not inside nested parentheses."""
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _parse_create(stmt: str) -> tuple[str, set[str]] | None:
    m = re.match(r"\s*create\s+table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z_][\w]*)\s*\(", stmt, re.I)
    if not m:
        return None
    body = _balanced(stmt, stmt.index("(", m.end() - 1))
    if body is None:
        return None
    cols: set[str] = set()
    for part in _split_top_level(body):
        tok = _IDENT.match(part.strip())
        if tok and tok.group(1).lower() not in _CONSTRAINT_HEADS:
            cols.add(tok.group(1))  # group(1) = the bare identifier, quotes stripped
    return m.group(1), cols


def _parse_insert(stmt: str) -> tuple[str, list[str]] | None:
    m = re.match(r"\s*insert\s+into\s+([a-zA-Z_][\w]*)\s*\(", stmt, re.I)
    if not m:
        return None
    body = _balanced(stmt, stmt.index("(", m.end() - 1))
    if body is None:
        return None
    cols = [c.strip().strip('"') for c in _split_top_level(body) if c.strip()]
    return m.group(1), cols


def lint(files: list[tuple[str, str]]) -> list[str]:
    """`files` = [(name, sql)] in apply order. Returns a list of human-readable errors."""
    known: dict[str, set[str]] = {}
    errors: list[str] = []
    for name, sql in files:
        for stmt in _statements(sql):
            created = _parse_create(stmt)
            if created:
                known[created[0]] = created[1]
                continue
            inserted = _parse_insert(stmt)
            if inserted:
                table, cols = inserted
                if table not in known:
                    errors.append(f"{name}: INSERT INTO `{table}` before any CREATE TABLE {table}")
                    continue
                missing = [c for c in cols if c not in known[table]]
                if missing:
                    errors.append(
                        f"{name}: INSERT INTO `{table}` names column(s) absent from its "
                        f"CREATE TABLE: {missing}"
                    )
    return errors


def lint_dir(path: Path) -> list[str]:
    files = [(p.name, p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.sql"))]
    return lint(files)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=str(PG_DIR), help="migration directory to lint")
    args = parser.parse_args(argv)
    errors = lint_dir(Path(args.dir))
    for e in errors:
        print(f"::error::{e}")
    if errors:
        print(f"\n{len(errors)} migration consistency error(s).")
        return 1
    print(f"eval-fabric migrations in {args.dir} are self-consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
