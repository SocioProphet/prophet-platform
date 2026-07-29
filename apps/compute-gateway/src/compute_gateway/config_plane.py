"""config_plane — the server half of the sovereign flag plane.

Noetica ships a client that resolves flags through
`local override > env > remote > built-in default` (Noetica#564). This is the remote
layer, and it lives in the gateway for one decisive reason: **the gateway already seals
hash-chained receipts**, so every flag change becomes provable evidence rather than a
silent mutation of production behaviour.

That is the whole differentiation. A commercial flag service can tell you a flag is off.
This one can prove *who turned it off, when, from what previous value, and in what order
relative to every other governed action* — because the change rides the same proof spine
as compute. "Kill-switches you can audit" is not a feature bolted on; it falls out of
putting the plane where the receipts already are.

Design constraints carried over from the client half:
  - Serving is UNAUTHENTICATED-readable but mutation is token-gated: a client that cannot
    reach the plane must degrade to its cached snapshot, so making reads hard would only
    make outages worse. Changing behaviour, however, is a governed act.
  - Scope (app/model/org) is honoured on read, so one plane serves many surfaces without a
    client ever receiving a snapshot meant for someone else.
  - State is stored through the SAME durable persistence the receipts use, so a restart
    cannot silently revert a kill-switch — the failure mode that would make the whole
    mechanism untrustworthy.
"""
from __future__ import annotations

import json
import time
from typing import Any

from . import persistence, receipts

FlagValue = bool | int | float | str

# Flags the plane is willing to serve. A plane that could invent flag NAMES would defeat
# the client's capability-surface guard by other means, so the authority is explicit and
# reviewed here, in code, rather than accumulated at runtime.
KNOWN_FLAGS: set[str] = {
    "voice.wake_word",
    "memory.banded",
    "compute.exhaust_accounting",
    "federation.enabled",
    "deliberation.controller",
}

_TABLE = "config_flags"


def _conn():  # pragma: no cover - thin wrapper over the shared store
    conn = persistence._conn()  # noqa: SLF001 — same package, one storage owner by design
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS {_TABLE} ("
        "scope TEXT NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL, "
        "value TEXT NOT NULL, actor TEXT, ts REAL, receipt_id TEXT, "
        "PRIMARY KEY (scope, name, kind))"
    )
    conn.commit()
    return conn


def scope_key(app: str = "noetica", model: str | None = None, org: str | None = None) -> str:
    """Scopes are ordered most-general → most-specific; resolution walks them in that order
    so a model- or org-specific value overrides the app default rather than colliding."""
    return "|".join([app, model or "*", org or "*"])


def _scope_chain(app: str, model: str | None, org: str | None) -> list[str]:
    chain = [scope_key(app)]
    if org:
        chain.append(scope_key(app, None, org))
    if model:
        chain.append(scope_key(app, model))
    if model and org:
        chain.append(scope_key(app, model, org))
    return chain


def get_snapshot(app: str = "noetica", model: str | None = None, org: str | None = None) -> dict[str, Any]:
    """The snapshot a client caches: flags + per-model kill-switches for this scope.

    Specific scopes win over general ones. Unknown flags are never emitted — the plane
    refuses to name a capability it has no authority over.
    """
    if not persistence.enabled():
        return {"flags": {}, "models": {}, "scope": {"app": app, "model": model, "org": org}, "served": False}
    conn = _conn()
    flags: dict[str, FlagValue] = {}
    models: dict[str, bool] = {}
    for scope in _scope_chain(app, model, org):  # general → specific
        for name, kind, raw in conn.execute(
            f"SELECT name, kind, value FROM {_TABLE} WHERE scope=?", (scope,)
        ).fetchall():
            value = json.loads(raw)
            if kind == "model":
                # Only a real boolean may drive a kill-switch. bool("false") is True, so
                # coercing here could flip a switch the wrong way on malformed state; a
                # non-boolean is ignored rather than guessed at.
                if isinstance(value, bool):
                    models[name] = value
            elif name in KNOWN_FLAGS:
                flags[name] = value
    return {"flags": flags, "models": models,
            "scope": {"app": app, "model": model, "org": org}, "served": True}


def set_flag(
    name: str, value: FlagValue, *, kind: str = "flag", actor: str = "operator",
    app: str = "noetica", model: str | None = None, org: str | None = None,
    project: str = "config-plane",
) -> dict[str, Any]:
    """Change a flag and SEAL the change.

    Returns the sealed receipt id alongside the previous value. The receipt is what makes
    this a governed act: an operator can always answer "what changed, from what, by whom,
    and where does it sit in the chain" without trusting a log that could be rewritten.

    Raises ValueError for an unknown flag — the plane's authority is explicit (KNOWN_FLAGS),
    so a typo cannot quietly create a flag nothing honours.
    """
    if kind == "flag" and name not in KNOWN_FLAGS:
        raise ValueError(f"unknown flag: {name}")
    if kind not in ("flag", "model"):
        raise ValueError(f"unknown kind: {kind}")
    if not persistence.enabled():
        raise RuntimeError("config plane requires durable storage (GATEWAY_STORE_DIR)")

    if kind == "model" and not isinstance(value, bool):
        raise ValueError("a model kill-switch must be a boolean")

    scope = scope_key(app, model if kind == "flag" else None, org)
    conn = _conn()

    # BEGIN IMMEDIATE takes the write lock BEFORE we read `previous`. Without it two
    # concurrent mutations of the same key both read the same prior value and seal
    # contradictory receipts — the chain would then disagree with itself about what the
    # value changed from. Read, seal, and write are one unit or none of them happen.
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            f"SELECT value FROM {_TABLE} WHERE scope=? AND name=? AND kind=?", (scope, name, kind)
        ).fetchone()
        previous = json.loads(row[0]) if row else None

        # Seal FIRST: a change that could not be receipted must not take effect. The receipt
        # is the authority for the change, not a description of it.
        receipt = receipts.seal(
            project,
            kind="config-change", backend="config-plane", runtime="gateway",
            inputs={"scope": scope, "name": name, "kind": kind, "previous": previous},
            outputs={"value": value},
            status="ok", actor=actor, epistemic_status="attested",
        )
        conn.execute(
            f"INSERT OR REPLACE INTO {_TABLE} (scope, name, kind, value, actor, ts, receipt_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (scope, name, kind, json.dumps(value), actor, time.time(), receipt.id),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        # The "ok" receipt is already in the chain and receipts are immutable by design, so
        # the only honest repair is to APPEND the contradiction rather than pretend it away:
        # a failed change that left an unqualified "ok" behind would make the chain lie.
        receipts.seal(
            project,
            kind="config-change", backend="config-plane", runtime="gateway",
            inputs={"scope": scope, "name": name, "kind": kind, "reverts": True},
            outputs={"error": str(exc)},
            status="error", actor=actor, epistemic_status="observed",
        )
        raise

    return {"name": name, "kind": kind, "scope": scope, "previous": previous,
            "value": value, "receipt": receipt.id, "actor": actor}


def history(limit: int = 50) -> list[dict[str, Any]]:
    """Current state with the receipt that put each value there — the audit surface.

    This is deliberately the CURRENT row per (scope,name,kind), not a change log: the full
    history already exists, immutably, in the receipt chain. Duplicating it here would
    create a second version of the truth that could drift from the sealed one.
    """
    if not persistence.enabled():
        return []
    rows = _conn().execute(
        f"SELECT scope, name, kind, value, actor, ts, receipt_id FROM {_TABLE} "
        "ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [
        {"scope": s, "name": n, "kind": k, "value": json.loads(v),
         "actor": a, "ts": ts, "receipt": rid}
        for (s, n, k, v, a, ts, rid) in rows
    ]
