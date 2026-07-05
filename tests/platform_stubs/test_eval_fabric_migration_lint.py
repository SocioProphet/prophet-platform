"""Tests for the eval-fabric migration linter (tools/lint_eval_fabric_migrations.py).

The real-dir test is a regression gate: it fails if any Postgres migration inserts into a
table with no prior CREATE, or names an insert column absent from the CREATE — the exact bug
class that shipped four times (metric_crosswalks + methodology_snapshots + repro_ledger_entries
+ causal_attributions). The synthetic tests prove the linter's own logic. No database needed.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _lint():
    path = ROOT / "tools" / "lint_eval_fabric_migrations.py"
    spec = importlib.util.spec_from_file_location("lint_eval_fabric_migrations", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_real_postgres_migrations_are_self_consistent():
    lint = _lint()
    errors = lint.lint_dir(ROOT / "infra" / "datastores" / "postgres")
    assert errors == [], "eval-fabric migration inconsistency:\n" + "\n".join(errors)


def test_flags_insert_before_create():
    lint = _lint()
    errors = lint.lint([("005_x.sql", "insert into ghost (a, b) values ('1', '2');")])
    assert any("before any CREATE TABLE ghost" in e for e in errors)


def test_flags_an_insert_column_absent_from_the_create():
    lint = _lint()
    files = [
        ("001.sql", "create table if not exists t (a text, b text);"),
        ("002.sql", "insert into t (a, c) values ('1', '2');"),
    ]
    errors = lint.lint(files)
    assert any("column(s) absent" in e and "'c'" in e for e in errors)


def test_accepts_a_consistent_create_then_insert():
    lint = _lint()
    files = [
        ("001.sql", "create table if not exists t (a text primary key, b text);"),
        ("002.sql", "insert into t (a, b) values ('1', '2');"),
    ]
    assert lint.lint(files) == []


def test_inline_constrained_column_is_a_column_not_a_constraint():
    # `id text primary key` is a column; a table-level `primary key (id)` is not.
    lint = _lint()
    files = [
        ("001.sql", "create table t (id text primary key, x jsonb not null, primary key (id));"),
        ("002.sql", "insert into t (id, x) values ('a', '{}');"),
    ]
    assert lint.lint(files) == []


def test_quoted_reserved_word_column_is_recognized():
    # `window` is a Postgres reserved word → quoted everywhere; the linter normalizes quotes so
    # a quoted CREATE column matches a quoted INSERT column.
    lint = _lint()
    files = [
        ("001.sql", 'create table t (id text primary key, "window" text not null);'),
        ("002.sql", 'insert into t (id, "window") values (\'a\', \'x\');'),
    ]
    assert lint.lint(files) == []


def test_ignores_comments():
    lint = _lint()
    files = [
        ("001.sql", "-- insert into ghost (a) values ('x');\ncreate table t (a text);"),
        ("002.sql", "insert into t (a) values ('1');"),
    ]
    assert lint.lint(files) == []
