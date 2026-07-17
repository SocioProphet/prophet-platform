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
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

# Decision thresholds on the blended similarity score.
MERGE = 0.90        # ≥ → auto-merge candidate (MERGE_VERIFIED, subject to margin + prime-topic admissibility)
REVIEW = 0.75       # ≥ → human review queue (REQUIRES_REVIEW)
MIN_MARGIN = 0.08   # Δ = best − second-best must exceed this to promote (else the match is ambiguous → review)
NAME_W, ATTR_W = 0.7, 0.3

# REGIS replay pins — every response carries the (as_of, resolver, policy, template) tuple so a merge is
# REPLAYABLE: same inputs + same key ⇒ same output. Bump these when the algorithm/policy/survivorship change.
RESOLVER_VERSION = "1.1.0"   # scoring + margin + prime-veto engine
POLICY_VERSION = "1.0.0"     # thresholds (MERGE/REVIEW/MIN_MARGIN) + corroboration/prime-admissibility rules
TEMPLATE_VERSION = "1.0.0"   # survivorship authority template (most-attrs → widest-scope → id)


def replay_key(as_of: str | None = None) -> dict[str, str]:
    """The deterministic replay key pinned on every response (REGIS framework requirement)."""
    return {
        "as_of_time": as_of or datetime.now(timezone.utc).isoformat(),
        "resolver_version": RESOLVER_VERSION,
        "policy_version": POLICY_VERSION,
        "template_version": TEMPLATE_VERSION,
    }


@dataclass
class Record:
    id: str
    name: str
    attributes: dict[str, str] = field(default_factory=dict)
    # Identity-is-prime: a record belongs to a SCOPE and carries PRIME TOPICS (irreducible roles/contexts,
    # e.g. patient/parent/citizen/founder). Merges that would multiply disjoint primes across different
    # scopes are FORBIDDEN even on high evidence (identity-is-prime-reference §Merge admissibility).
    scope: str = ""
    primes: frozenset[str] = field(default_factory=frozenset)


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


def attr_agreement(a: dict[str, str], b: dict[str, str]) -> float:
    """Agreement over SHARED attribute keys: of the keys BOTH records carry, the fraction whose values match.
    Extra attributes on one side are neutral, not penalties (a richer record must not score *worse* against a
    sparse one) — that's the ER-correct signal, unlike raw Jaccard which punishes extra keys. 0 if no shared key."""
    shared = a.keys() & b.keys()
    if not shared:
        return 0.0
    agree = sum(1 for k in shared if _norm(a[k]) == _norm(b[k]) and a[k])
    return agree / len(shared)


def _conflict(a: Record, b: Record) -> str | None:
    """A hard disqualifier: the same identifying key with DIFFERENT non-empty values (email/dob/ssn/id)."""
    for key in ("email", "dob", "ssn", "national_id", "id_number"):
        va, vb = _norm(a.attributes.get(key, "")), _norm(b.attributes.get(key, ""))
        if va and vb and va != vb:
            return key
    return None


def _prime_veto(a: Record, b: Record) -> str | None:
    """Identity-is-prime merge admissibility (the doctrine classical ER lacks): some merges are FORBIDDEN
    even on high evidence. Merging two records with DISJOINT prime topics across DIFFERENT scopes would
    multiply irreducible roles across contexts (e.g. collapsing a 'patient'-scope record into a 'founder'-
    scope one just because names match) — cross-context leakage. Vetoed → MERGE_BLOCKED, not merged."""
    if a.primes and b.primes and not (a.primes & b.primes) and a.scope != b.scope:
        return "identity_prime_veto"
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
    attr_sim = attr_agreement(a.attributes, b.attributes)
    # No attribute signal on either side → the name carries the score (don't dilute it with a 0 attr term).
    has_attrs = bool(a.attributes) or bool(b.attributes)
    score = round(name_sim if not has_attrs else NAME_W * name_sim + ATTR_W * attr_sim, 4)
    matched = sorted({k for k in a.attributes if _norm(a.attributes.get(k, "")) == _norm(b.attributes.get(k, "")) and a.attributes.get(k)})
    exact_name = _norm(a.name) == _norm(b.name)
    conflict = _conflict(a, b)
    veto = _prime_veto(a, b)
    block_reason = conflict or veto
    if block_reason is not None:
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
        evidence={"blocking_key": blocking_key(a), "conflict_field": conflict,
                  "prime_veto": veto, "matched_attributes": matched},
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


def resolve(records: list[Record], as_of: str | None = None) -> dict[str, Any]:
    """Full ER pass, identity-is-prime-conformant: block → score → MARGIN-gated + prime-admissible merge →
    union-find clusters → survivorship → proof-carrying epistemic-edge records. Pins a replay key, and
    projects golden records + a concordance (source record → canonical entity) per the REGIS framework."""
    blocks: dict[str, list[Record]] = {}
    for r in records:
        blocks.setdefault(blocking_key(r), []).append(r)

    pairs: list[PairDecision] = []
    for block in blocks.values():
        for a, b in combinations(block, 2):
            d = score_pair(a, b)
            if d.decision != "NO_MATCH":
                pairs.append(d)

    # Per-record candidate scores → margin. The spec wants promotion by the score MARGIN Δ = best − second,
    # not an absolute cutoff: an auto-merge must be DECISIVELY the best match, not one of several near-ties.
    cand: dict[str, list[tuple[float, str]]] = {}
    for d in pairs:
        cand.setdefault(d.a, []).append((d.score, d.b))
        cand.setdefault(d.b, []).append((d.score, d.a))
    for lst in cand.values():
        lst.sort(reverse=True)

    def margin(rid: str, other: str) -> float:
        lst = cand.get(rid, [])
        if not lst or lst[0][1] != other:
            return -1.0  # `other` is not rid's top candidate → not a decisive match from rid's side
        second = lst[1][0] if len(lst) > 1 else 0.0
        return lst[0][0] - second

    uf = _UF()
    for r in records:
        uf.find(r.id)  # every record is at least its own entity
    for d in pairs:
        if d.decision != "MERGE_VERIFIED":
            continue
        # Attribute-corroborated merges are safe to auto-apply even amid ties (the matched attribute IS the
        # disambiguator). But a NAME-ONLY merge amid near-ties is dangerous — many distinct people share a
        # name — so it must be the MUTUAL decisive best (Δ ≥ MIN_MARGIN both sides) or it goes to review.
        if d.evidence.get("matched_attributes"):
            uf.union(d.a, d.b)
            continue
        ma, mb = margin(d.a, d.b), margin(d.b, d.a)
        if ma >= MIN_MARGIN and mb >= MIN_MARGIN:
            uf.union(d.a, d.b)
        else:
            d.decision = "REQUIRES_REVIEW"  # ambiguous name-only match — human review
            d.evidence["ambiguous_margin"] = round(max(ma, mb), 4)

    # Clusters + SURVIVORSHIP: the surviving record (most attributes, then widest scope, then id) is canonical;
    # its values win attribute conflicts, other members' attributes fill gaps.
    by_id = {r.id: r for r in records}
    clusters: dict[str, list[str]] = {}
    for r in records:
        clusters.setdefault(uf.find(r.id), []).append(r.id)
    entities: list[dict[str, Any]] = []
    for root, members in clusters.items():
        recs = [by_id[m] for m in members]
        survivor = max(recs, key=lambda r: (len(r.attributes), r.scope, r.id))
        attrs: dict[str, str] = {}
        for r in recs:
            for k, v in r.attributes.items():
                attrs.setdefault(k, v)   # first-seen fills gaps
        attrs.update(survivor.attributes)  # survivor wins conflicts
        entities.append({
            "entity_id": f"ent:{root}", "members": sorted(members), "size": len(members),
            "canonical": {"survivor": survivor.id, "name": survivor.name, "attributes": attrs,
                          "scope": survivor.scope, "primes": sorted(survivor.primes)},
        })

    # Golden records (canonical projection keyed by entity) + concordance/crosswalk (source id → entity).
    golden_records = {
        e["entity_id"]: {**e["canonical"], "members": e["members"]} for e in entities
    }
    concordance = [
        {"record_id": m, "entity_id": e["entity_id"], "survivor": e["canonical"]["survivor"]}
        for e in entities for m in e["members"]
    ]

    # Proof-carrying epistemic-edge records for each merge (regis epistemic-edge typing): a same_as edge
    # with its epistemic class + confidence, so a merge is an auditable derived relation, not a black box.
    edges = [
        {"subject": d.a, "predicate": "same_as", "object": d.b,
         "epistemic_class": "derived_relation", "confidence_type": "similarity",
         "confidence_level": d.score, "evidence": d.evidence}
        for d in pairs if d.decision == "MERGE_VERIFIED"
    ]

    return {
        "replay_key": replay_key(as_of),
        "records": len(records),
        "entities": entities,
        "golden_records": golden_records,
        "concordance": concordance,
        "merged": sum(1 for e in entities if e["size"] > 1),
        "decision_ledger": [d.__dict__ for d in pairs],
        "epistemic_edges": edges,
        "review_queue": [d.__dict__ for d in pairs if d.decision == "REQUIRES_REVIEW"],
        "blocked": [d.__dict__ for d in pairs if d.decision == "MERGE_BLOCKED"],
    }


def _anchor_record(golden: dict[str, Any]) -> Record:
    """Turn a prior golden record into an anchor Record so new inputs can be scored against it."""
    return Record(
        id=golden["entity_id"] if "entity_id" in golden else golden["survivor"],
        name=golden["name"], attributes=dict(golden.get("attributes", {})),
        scope=golden.get("scope", ""), primes=frozenset(golden.get("primes", [])),
    )


def resolve_incremental(prior_golden: list[dict[str, Any]], new_records: list[Record],
                        as_of: str | None = None) -> dict[str, Any]:
    """INCREMENTAL delta resolution: score only the NEW records (against each other + prior golden anchors),
    never re-resolving the settled estate. Returns which new records attached to an existing entity vs formed
    new ones — the O(new) update the REGIS framework asks for instead of an O(n²) full re-run."""
    anchors = [_anchor_record(g) for g in prior_golden]
    anchor_ids = {a.id for a in anchors}
    universe = anchors + new_records
    new_ids = {r.id for r in new_records}

    blocks: dict[str, list[Record]] = {}
    for r in universe:
        blocks.setdefault(blocking_key(r), []).append(r)

    uf = _UF()
    for r in universe:
        uf.find(r.id)
    delta_pairs: list[PairDecision] = []
    for block in blocks.values():
        for a, b in combinations(block, 2):
            # Skip anchor↔anchor: the prior estate is already resolved — only NEW-involving pairs are work.
            if a.id in anchor_ids and b.id in anchor_ids:
                continue
            d = score_pair(a, b)
            if d.decision == "NO_MATCH":
                continue
            delta_pairs.append(d)
            if d.decision == "MERGE_VERIFIED":
                uf.union(a.id, b.id)

    # Classify each new record: attached to a prior entity (its cluster contains an anchor) or a new entity.
    by_id = {r.id: r for r in universe}
    attached: list[dict[str, Any]] = []
    new_entities: dict[str, list[str]] = {}
    for r in new_records:
        root = uf.find(r.id)
        members = [m for m in by_id if uf.find(m) == root]
        prior_anchor = next((m for m in members if m in anchor_ids), None)
        if prior_anchor is not None:
            attached.append({"record_id": r.id, "entity_id": prior_anchor})
        else:
            new_entities.setdefault(root, [])
            new_entities[root] = sorted(m for m in members if m in new_ids)

    return {
        "replay_key": replay_key(as_of),
        "new_records": len(new_records),
        "attached_to_existing": attached,
        "new_entities": [{"entity_id": f"ent:{root}", "members": mem} for root, mem in new_entities.items()],
        "delta_ledger": [d.__dict__ for d in delta_pairs],
        "review_queue": [d.__dict__ for d in delta_pairs if d.decision == "REQUIRES_REVIEW"],
        "blocked": [d.__dict__ for d in delta_pairs if d.decision == "MERGE_BLOCKED"],
    }
