"""Entity Resolution engine — the resolver regis-entity-graph never had.

regis-entity-graph ships schemas + validators that check a MERGE decision is *well-formed*, but nothing
that PRODUCES one. This is the engine: blocking → pairwise similarity → union-find clustering → a
decision per candidate pair (MERGE_VERIFIED / REQUIRES_REVIEW / MERGE_BLOCKED), each carrying the
field-level match evidence + scores as provenance. That's the moat over Senzing/Neo4j ER: every merge
is a replayable, proof-carrying certificate, not just a black-box score.

Pure + dependency-free (Jaro-Winkler + token-Jaccard hand-rolled) so it's trivially testable and fast.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

# Decision thresholds on the blended similarity score.
MERGE = 0.90        # ≥ → auto-merge (MERGE_VERIFIED)
REVIEW = 0.75       # ≥ → human review queue (REQUIRES_REVIEW)
NAME_W, ATTR_W = 0.7, 0.3


@dataclass
class Record:
    id: str
    name: str
    attributes: dict[str, str] = field(default_factory=dict)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^\w]+", _norm(s)) if t}


def jaro(a: str, b: str) -> float:
    """Jaro string similarity in [0,1]."""
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
    md = max(len(a), len(b)) // 2 - 1
    a_match = [False] * len(a)
    b_match = [False] * len(b)
    matches = 0
    for i, ca in enumerate(a):
        for j in range(max(0, i - md), min(i + md + 1, len(b))):
            if not b_match[j] and b[j] == ca:
                a_match[i] = b_match[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    t = 0
    k = 0
    for i, ca in enumerate(a):
        if a_match[i]:
            while not b_match[k]:
                k += 1
            if ca != b[k]:
                t += 1
            k += 1
    t /= 2
    return (matches / len(a) + matches / len(b) + (matches - t) / matches) / 3


def jaro_winkler(a: str, b: str, p: float = 0.1) -> float:
    """Jaro-Winkler — boosts common-prefix matches (good for names)."""
    j = jaro(a, b)
    pref = 0
    for ca, cb in zip(a, b):
        if ca == cb and pref < 4:
            pref += 1
        else:
            break
    return j + pref * p * (1 - j)


def jaccard(a: dict[str, str], b: dict[str, str]) -> float:
    """Token-Jaccard over the attribute key=value tokens (0 if neither has attributes)."""
    ta = {f"{k}={_norm(v)}" for k, v in a.items()}
    tb = {f"{k}={_norm(v)}" for k, v in b.items()}
    if not ta and not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _conflict(a: Record, b: Record) -> str | None:
    """A hard disqualifier: the same identifying key with DIFFERENT non-empty values (email/dob/ssn/id)."""
    for key in ("email", "dob", "ssn", "national_id", "id_number"):
        va, vb = _norm(a.attributes.get(key, "")), _norm(b.attributes.get(key, ""))
        if va and vb and va != vb:
            return key
    return None


def blocking_key(r: Record) -> str:
    """Cheap block so we compare O(block²) not O(n²): first 3 chars of the normalized name + first token."""
    n = _norm(r.name)
    toks = _tokens(r.name)
    first = min(toks) if toks else ""
    return f"{n[:3]}|{first[:4]}"


@dataclass
class PairDecision:
    a: str
    b: str
    decision: str          # MERGE_VERIFIED | REQUIRES_REVIEW | MERGE_BLOCKED
    score: float
    name_sim: float
    attr_sim: float
    evidence: dict[str, Any]


def score_pair(a: Record, b: Record) -> PairDecision:
    name_sim = jaro_winkler(_norm(a.name), _norm(b.name))
    attr_sim = jaccard(a.attributes, b.attributes)
    # No attribute signal on either side → the name carries the score (don't dilute it with a 0 attr term).
    has_attrs = bool(a.attributes) or bool(b.attributes)
    score = round(name_sim if not has_attrs else NAME_W * name_sim + ATTR_W * attr_sim, 4)
    matched = sorted({k for k in a.attributes if _norm(a.attributes.get(k, "")) == _norm(b.attributes.get(k, "")) and a.attributes.get(k)})
    exact_name = _norm(a.name) == _norm(b.name)
    conflict = _conflict(a, b)
    if conflict is not None:
        decision = "MERGE_BLOCKED"
    # Auto-merge requires CORROBORATION — a strong name match alone (fuzzy) is only a review candidate,
    # because two different people can share a near-identical name. Exact name OR a matched attribute merges.
    elif score >= MERGE and (exact_name or matched):
        decision = "MERGE_VERIFIED"
    elif score >= REVIEW:
        decision = "REQUIRES_REVIEW"
    else:
        decision = "NO_MATCH"
    return PairDecision(
        a=a.id, b=b.id, decision=decision, score=score,
        name_sim=round(name_sim, 4), attr_sim=round(attr_sim, 4),
        evidence={"blocking_key": blocking_key(a), "conflict_field": conflict, "matched_attributes": matched},
    )


class _UF:
    def __init__(self) -> None:
        self.p: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: str, b: str) -> None:
        self.p[self.find(a)] = self.find(b)


def resolve(records: list[Record]) -> dict[str, Any]:
    """Full ER pass: block → score candidate pairs → union-find MERGE_VERIFIED → emit entities + ledger."""
    blocks: dict[str, list[Record]] = {}
    for r in records:
        blocks.setdefault(blocking_key(r), []).append(r)

    ledger: list[PairDecision] = []
    uf = _UF()
    for r in records:
        uf.find(r.id)  # every record is at least its own entity
    for block in blocks.values():
        for a, b in combinations(block, 2):
            d = score_pair(a, b)
            if d.decision == "NO_MATCH":
                continue
            ledger.append(d)
            if d.decision == "MERGE_VERIFIED":
                uf.union(a.id, b.id)

    # entities = union-find clusters; each carries its member record ids.
    clusters: dict[str, list[str]] = {}
    for r in records:
        clusters.setdefault(uf.find(r.id), []).append(r.id)
    entities = [
        {"entity_id": f"ent:{root}", "members": sorted(members), "size": len(members)}
        for root, members in clusters.items()
    ]
    return {
        "records": len(records),
        "entities": entities,
        "merged": sum(1 for e in entities if e["size"] > 1),
        "decision_ledger": [d.__dict__ for d in ledger],
        "review_queue": [d.__dict__ for d in ledger if d.decision == "REQUIRES_REVIEW"],
        "blocked": [d.__dict__ for d in ledger if d.decision == "MERGE_BLOCKED"],
    }
