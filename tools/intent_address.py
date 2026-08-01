"""The bridge: the 23x6 intent grid as a slice of the coordinate algebra.

The intent grid (Noetica `agent-machine/lib/intent-grid.ts`) is a derived, grounded,
falsifiable capability matrix — but it is *flat*: it has no metric on its rows (which
intents are near?) and no abstraction ordering. This module lifts each intent row into
a `SemanticAddress`, so the grid inherits exactly the two properties it lacked and the
kernel already has:

  * a computed metric — intents that do the same kind of work (share a column) cluster
    at distance 1; intents in different columns sit at distance 2. Nothing learned,
    nothing curated per pair.
  * a layer — the meta row `conversation_objective` is *second-order* (its operand is
    an action, not a topic), so its address is built one layer up, out of an action
    address. The self-referential row is a genuine fixed point in the grading.

And it makes the grid's headline finding structural: `sense` (world:read) is the
estate's thinnest column. Route a world:read query when the sense intents are absent
and `bind_tiered` returns BOTTOM — the wiring gap becomes an honest abstention, not a
silent mis-route.

The column algebra, made explicit: a column = a polarity (read=pullback / write=pushout)
over a substrate, and the three substrates are Peircean — held=Firstness (the present
working register), world=Secondness (brute external fact), store=Thirdness (the
persisted, mediating law). Six columns = two dual operators x three substrates.

This is a demonstration/bridge in the algebra's own repo; it encodes the intent roster
as data (the canon lives in Noetica) and does not import from Noetica.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from tools.semantic_algebra import (
    ACT,
    BOTTOM,
    FST,
    NIL,
    POT,
    PRIMITIVES,
    SND,
    TRD,
    SemanticAddress,
    Term,
    TermSet,
    add,
    bind_tiered,
    distance,
    mul,
    prim,
)

# --------------------------------------------------------------------------- #
# The six columns = {read: pullback, write: pushout} x {held, world, store}
# --------------------------------------------------------------------------- #

#: Substrate -> Peircean primitive. held=Firstness, world=Secondness, store=Thirdness.
SUBSTRATE_PRIM: Dict[str, str] = {"held": FST, "world": SND, "store": TRD}

#: Polarity -> primitive marker. read is receptive (potentiality), write effective (act).
POLARITY_PRIM: Dict[str, str] = {"read": POT, "write": ACT}

#: The six ACTION_SIGNATURE columns, each as (substrate, polarity).
COLUMNS: Dict[str, Tuple[str, str]] = {
    "sense":     ("world", "read"),
    "execute":   ("world", "write"),
    "retrieve":  ("store", "read"),
    "create":    ("store", "write"),
    "evaluate":  ("held", "read"),
    "transform": ("held", "write"),
}


def column_anchor(column: str) -> Term:
    """The layer-1 anchor for a column: substrate primitive x polarity marker."""
    substrate, polarity = COLUMNS[column]
    return mul(prim(SUBSTRATE_PRIM[substrate]), prim(POLARITY_PRIM[polarity]))


# --------------------------------------------------------------------------- #
# The 23 rows, by primary column (Noetica intent-router INTENT_ACTION grouping)
# --------------------------------------------------------------------------- #

#: Intent -> its primary action-column. `everyday` is retained here but its action
#: profile is a STRICT subset of explain_teach, so the canon collapses it under
#: minimality; the canonical grid is 22 topics + 1 meta = 23 x 6 = 138 (pinned in
#: intent-grid.ts, not re-derived here).
INTENT_PRIMARY: Dict[str, str] = {
    # retrieve (store:read)
    "qa_over_doc": "retrieve", "research_lookup": "retrieve", "summarize_doc": "retrieve",
    "self_identity": "retrieve", "meta_capability": "retrieve", "file_ops": "retrieve",
    "everyday": "retrieve",
    # evaluate (held:read)
    "review_audit": "evaluate", "compare_benchmark": "evaluate", "code_review": "evaluate",
    "status_check": "evaluate",
    # create (store:write)
    "build_implement": "create", "preferences_memory": "create",
    # transform (held:write)
    "fix_debug": "transform", "explain_teach": "transform", "write_draft": "transform",
    "compute_math": "transform", "prove_reason": "transform",
    # sense (world:read) -- the thinnest column
    "file_ingest": "sense",
    # execute (world:write)
    "configure_ops": "execute",
    # second-order intents (the meta/embedding group)
    "plan_nextsteps": "meta", "converse_smalltalk": "meta", "confirm_steer": "meta",
}

#: The +1 meta row — second-order: its operand is an action, not a topic.
META_ROW = "conversation_objective"

#: Distinct layer-1 disambiguators (one per intent), so same-column intents are
#: neighbours differing only in their differentia — the role whose very meaning is
#: "what distinguishes this within its genus".
_DISAMBIGUATORS: List[Term] = [mul(prim(a), prim(b)) for a in PRIMITIVES for b in PRIMITIVES]

#: A layer-1 anchor for the meta-action group, deliberately NIL-grounded so it is
#: distinct from all six column anchors (which ground on FST/SND/TRD) — these rows must
#: never be mis-counted under, or mis-routed to, a real column.
_META_COLUMN_ANCHOR = mul(prim(NIL), prim(TRD))


def build_intent_addresses() -> Dict[str, SemanticAddress]:
    """Address every intent row. Topic intents at layer 2; the meta row at layer 3.

    Same-column intents land at distance 1; cross-column at distance 2. The meta row
    is built out of an action address, so it sits one layer up — the second-order
    row is a fixed point in the grading, comparable only to other second-order rows.
    """
    addrs: Dict[str, SemanticAddress] = {}
    for i, (name, column) in enumerate(sorted(INTENT_PRIMARY.items())):
        ground = _META_COLUMN_ANCHOR if column == "meta" else column_anchor(column)
        term = mul(ground, _DISAMBIGUATORS[i])
        addrs[name] = SemanticAddress(
            term=term, iri=f"intent://{name}", inference="asserted", mood="assert"
        )
    # the meta row's operand IS an action address -> one layer up
    action_term = addrs["plan_nextsteps"].term  # a layer-2 action address
    addrs[META_ROW] = SemanticAddress(
        term=mul(action_term, action_term),
        iri=f"intent://{META_ROW}",
        inference="abduced",
        mood="assert",
    )
    return addrs


# --------------------------------------------------------------------------- #
# What the flat grid could not do
# --------------------------------------------------------------------------- #


def intent_distance(a: SemanticAddress, b: SemanticAddress) -> int:
    """Structural distance between two intent addresses (same layer only)."""
    return distance(a.term, b.term)


def route(query_column: str, addresses: Dict[str, SemanticAddress]) -> "Term | object":
    """Ground a by-column query to an intent under that column, or abstain.

    Returns the admitted intent's term, or BOTTOM when the column has no intent in
    `addresses` — which is exactly what makes the `sense` wiring gap show up as an
    honest abstention rather than a mis-route.
    """
    topic_terms = [
        addr.term for name, addr in addresses.items()
        if name != META_ROW and addr.term.layer == 2  # layer-2 topic rows
    ]
    upper = add(*[column_anchor(c) for c in COLUMNS])
    lower = add(*topic_terms)
    return bind_tiered(column_anchor(query_column), upper, lower)


def column_fill(addresses: Dict[str, SemanticAddress]) -> Dict[str, int]:
    """How many intents sit under each column (their primary), by address ground."""
    fill = {c: 0 for c in COLUMNS}
    anchors = {column_anchor(c).code(): c for c in COLUMNS}
    for name, addr in addresses.items():
        if name == META_ROW or addr.term.layer != 2:
            continue
        ground = addr.term.roles()["ground"]
        col = anchors.get(ground.code())
        if col is not None:
            fill[col] += 1
    return fill
