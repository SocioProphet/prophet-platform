"""identity-prime kernel.

Promoted from the proven toy reference impl (``identity_is_prime_reference``,
``src/prime_er/``) into ``prophet-platform`` as a clean, self-contained module.

What is preserved (the PROVEN behavior of the Michael trace):

  * prime-topic basis        -> identity-as-prime encode/decode (``primes`` here)
  * policy veto              -> forbidden prime-pair / feature-key / sensitive-
                                prime-in-ad-realm checks (``Policy``)
  * entity resolution        -> blocking + stable-exclusive conflict + policy
                                veto on merges (``resolve_entities``)
  * bounded congruence leak  -> modular nonce-stream reachability (``NonceStream``)

What is intentionally DEFERRED (out of scope for this kernel promotion):

  * surface343 projection
  * naming_projection
  * the recommendation loop

The crucial difference from the reference: the emitted artifact is bound to the
CANONICAL platform schema (``schemas/proof-artifact.schema.json``, v0.1), NOT the
simpler toy schema. See ``emit_proof_artifact`` for the toy -> canonical mapping.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Prime-topic basis ("identity is prime")
# ---------------------------------------------------------------------------

_DEFAULT_PRIMES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

# Canonical small topic set used by the Michael trace and examples.
DEFAULT_TOPICS: List[Tuple[str, int]] = [
    ("FOUNDER", _DEFAULT_PRIMES[0]),
    ("PATIENT", _DEFAULT_PRIMES[1]),
    ("PARENT", _DEFAULT_PRIMES[2]),
    ("CITIZEN", _DEFAULT_PRIMES[3]),
    ("CREATOR", _DEFAULT_PRIMES[4]),
]


def encode_topics(active: Iterable[str], topics: Sequence[Tuple[str, int]] = DEFAULT_TOPICS) -> int:
    """Encode active topics into a uniquely-factorable integer.

    Makes 'identity is prime' literal: the factorization recovers the topics.
    """
    m = {name: prime for name, prime in topics}
    out = 1
    for name in active:
        if name not in m:
            raise KeyError(f"Unknown prime topic: {name}")
        out *= m[name]
    return out


def decode_topics(code: int, topics: Sequence[Tuple[str, int]] = DEFAULT_TOPICS) -> List[str]:
    """Recover topics from a code produced by :func:`encode_topics`."""
    if code < 1:
        raise ValueError("code must be a positive integer")
    out: List[str] = []
    remaining = code
    for name, prime in topics:
        while remaining % prime == 0:
            out.append(name)
            remaining //= prime
    if remaining != 1:
        out.append(f"UNKNOWN_FACTOR({remaining})")
    return out


# ---------------------------------------------------------------------------
# Event-IR (minimal, in-module copy of the reference shape)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scope:
    device: str = ""
    app: str = ""
    realm: str = ""
    jurisdiction: str = ""

    @staticmethod
    def from_obj(obj: Dict[str, Any]) -> "Scope":
        obj = obj or {}
        return Scope(
            device=str(obj.get("device", "")),
            app=str(obj.get("app", "")),
            realm=str(obj.get("realm", "")),
            jurisdiction=str(obj.get("jurisdiction", "")),
        )


@dataclass(frozen=True)
class Event:
    ts: str
    actor: str
    scope: Scope
    action: str
    primes: List[str]
    attrs: Dict[str, Any]
    evidence: Dict[str, Any]

    @staticmethod
    def from_obj(obj: Dict[str, Any]) -> "Event":
        return Event(
            ts=str(obj.get("ts", "")),
            actor=str(obj.get("actor", "")),
            scope=Scope.from_obj(obj.get("scope", {})),
            action=str(obj.get("action", "")),
            primes=list(obj.get("primes", []) or []),
            attrs=dict(obj.get("attrs", {}) or {}),
            evidence=dict(obj.get("evidence", {}) or {}),
        )


def load_events_jsonl(text: str) -> List[Event]:
    """Parse a JSONL Event-IR trace (one event object per line)."""
    events: List[Event] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(Event.from_obj(json.loads(line)))
    return events


# ---------------------------------------------------------------------------
# Policy veto layer (the "polytope" constraint surface)
# ---------------------------------------------------------------------------


def _canon(s: str) -> str:
    return (s or "").strip().upper()


@dataclass(frozen=True)
class Policy:
    forbidden_prime_pairs: Set[frozenset] = field(default_factory=set)
    ad_realm_markers: Tuple[str, ...] = ("ADTECH", "ADS", "MARKETING", "TRACK")
    forbidden_feature_keys_by_prime: Dict[str, Set[str]] = field(default_factory=dict)

    def is_ad_realm(self, realm: str) -> bool:
        r = _canon(realm)
        return any(m in r for m in self.ad_realm_markers)

    def normalize_primes(self, primes: Sequence[str], realm: str) -> Set[str]:
        p = {_canon(x) for x in (primes or []) if _canon(x)}
        if self.is_ad_realm(realm):
            p.add("ADS")
        return p

    def violates_prime_pairs(self, primes: Iterable[str]) -> List[Tuple[str, str]]:
        s = set(primes)
        bad: List[Tuple[str, str]] = []
        for pair in self.forbidden_prime_pairs:
            if pair.issubset(s):
                a, b = sorted(list(pair))
                bad.append((a, b))
        return bad

    def event_violations(self, ev: Event) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        primes = self.normalize_primes(ev.primes, ev.scope.realm)

        for a, b in self.violates_prime_pairs(primes):
            violations.append({
                "kind": "FORBIDDEN_PRIME_COOC",
                "details": {"pair": [a, b], "primes": sorted(list(primes))},
            })

        attrs_keys = {_canon(k) for k in (ev.attrs or {}).keys()}
        for p, bad_keys in self.forbidden_feature_keys_by_prime.items():
            if _canon(p) in primes:
                overlap = sorted(list(attrs_keys.intersection({_canon(k) for k in bad_keys})))
                if overlap:
                    violations.append({
                        "kind": "FORBIDDEN_FEATURE_FOR_PRIME",
                        "details": {"prime": _canon(p), "keys": overlap},
                    })

        if self.is_ad_realm(ev.scope.realm):
            if "PATIENT" in primes or "PARENT" in primes:
                violations.append({
                    "kind": "SENSITIVE_PRIME_IN_AD_REALM",
                    "details": {"realm": ev.scope.realm, "primes": sorted(list(primes))},
                })

        return violations

    def merge_allowed(
        self,
        primes_a: Sequence[str],
        primes_b: Sequence[str],
        realm_a: str,
        realm_b: str,
    ) -> bool:
        pa = self.normalize_primes(primes_a, realm_a)
        pb = self.normalize_primes(primes_b, realm_b)
        merged = pa.union(pb)
        return len(self.violates_prime_pairs(merged)) == 0


def default_policy() -> Policy:
    """The proven default policy from the reference Michael trace."""
    forbidden = {
        frozenset(["PATIENT", "ADS"]),
        frozenset(["PARENT", "ADS"]),
        frozenset(["CITIZEN", "ADS"]),
    }
    forbidden_feature = {
        "PATIENT": {"THIRD_PARTY_COOKIE", "AD_ID", "PIXEL_ID"},
        "PARENT": {"THIRD_PARTY_COOKIE", "AD_ID", "PIXEL_ID"},
    }
    return Policy(
        forbidden_prime_pairs=forbidden,
        forbidden_feature_keys_by_prime=forbidden_feature,
    )


# ---------------------------------------------------------------------------
# Entity resolution (blocking + stable-exclusive conflict + policy veto)
# ---------------------------------------------------------------------------


@dataclass
class MergeReason:
    kind: str  # MATCH | POSSIBLE_MATCH | BLOCKED | UNRELATED
    match_key: str


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, a: int) -> int:
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def _stable_exclusive_conflict(a: Event, b: Event) -> bool:
    ea = (a.attrs or {}).get("email")
    eb = (b.attrs or {}).get("email")
    if ea and eb and str(ea).lower() != str(eb).lower():
        return True
    return False


def _blocking_tokens(ev: Event) -> Set[str]:
    out: Set[str] = set()
    for k in ("email", "phone", "device_id", "cookie_id"):
        v = (ev.attrs or {}).get(k)
        if v:
            out.add(f"{k}:{str(v).lower()}")
    return out


def resolve_entities(
    events: Sequence[Event],
    policy: Policy,
) -> Tuple[List[int], Dict[Tuple[int, int], MergeReason]]:
    """Resolve events into entity clusters with a policy veto on merges.

    Candidates are selected by shared blocking tokens; a stable-exclusive
    conflict (e.g. differing emails) hard-blocks a merge, and the prime-topic
    policy veto blocks merges that would create a forbidden prime mixture.
    """
    n = len(events)
    uf = _UnionFind(n)
    reasons: Dict[Tuple[int, int], MergeReason] = {}
    index: Dict[str, List[int]] = {}

    for i, ev in enumerate(events):
        candidates: Set[int] = set()
        for tok in _blocking_tokens(ev):
            for j in index.get(tok, []):
                candidates.add(j)

        for j in sorted(candidates):
            other = events[j]
            shared = sorted(_blocking_tokens(ev).intersection(_blocking_tokens(other)))
            match_key = "+".join(t.split(":", 1)[0].upper() for t in shared) or "NONE"

            if _stable_exclusive_conflict(ev, other):
                reasons[(j, i)] = MergeReason(kind="BLOCKED", match_key="CONTRADICTION:email")
                continue

            kind = "MATCH" if shared else "UNRELATED"
            if kind == "MATCH" and not policy.merge_allowed(
                ev.primes, other.primes, ev.scope.realm, other.scope.realm
            ):
                kind = "BLOCKED"

            reasons[(j, i)] = MergeReason(kind=kind, match_key=match_key)
            if kind == "MATCH":
                uf.union(i, j)

        for tok in _blocking_tokens(ev):
            index.setdefault(tok, []).append(i)

    root_to_id: Dict[int, int] = {}
    entity_ids: List[int] = []
    next_id = 1
    for i in range(n):
        r = uf.find(i)
        if r not in root_to_id:
            root_to_id[r] = next_id
            next_id += 1
        entity_ids.append(root_to_id[r])

    return entity_ids, reasons


# ---------------------------------------------------------------------------
# Bounded congruence (modular nonce-stream leak detection)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NonceStream:
    """A modular arithmetic stream: n_{i+1} = n_i + delta (mod m)."""

    base: int
    delta: int
    m: int
    max_steps: int = 1000

    def steps_to(self, x: int) -> Optional[int]:
        """Minimal k s.t. x == base + k*delta (mod m), if k <= max_steps."""
        if self.m <= 0:
            raise ValueError("m must be positive")
        rhs = (x - self.base) % self.m
        delta = self.delta % self.m
        if delta == 0:
            k0: Optional[int] = 0 if rhs == 0 else None
        else:
            from math import gcd

            g = gcd(delta, self.m)
            if rhs % g != 0:
                k0 = None
            else:
                m_p = self.m // g
                inv = pow(delta // g, -1, m_p)
                k0 = (inv * (rhs // g)) % m_p
        if k0 is None:
            return None
        return k0 if k0 <= self.max_steps else None


def _log_bucket(k: int) -> int:
    import math

    return int(math.floor(math.log(max(1, k))))


# ---------------------------------------------------------------------------
# Canonical proof-artifact emission
# ---------------------------------------------------------------------------


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Toy reference status -> canonical schema ``result`` enum. Identity map: the
# toy already used the same three labels, and the canonical schema's enum is
# {PROVED, VIOLATION, INCONCLUSIVE}.
_STATUS_TO_RESULT = {
    "PROVED": "PROVED",
    "VIOLATION": "VIOLATION",
    "INCONCLUSIVE": "INCONCLUSIVE",
}

COMPILER_ID = "identity-prime-kernel/0.1.0"
PRODUCER_BOUNDARY = "prophet-platform/identity-prime"

# Default deny: the claim under test is information-flow containment of sensitive
# identity primes (PATIENT/PARENT/CITIZEN must not flow into ad realms).
CLAIM_KIND = "ifc_no_flow"


def analyze_trace(
    events: Sequence[Event],
    policy: Optional[Policy] = None,
    *,
    events_bytes: Optional[bytes] = None,
    policy_bytes: Optional[bytes] = None,
    max_steps: int = 1000,
) -> Dict[str, Any]:
    """Run ER + policy veto + bounded-congruence leak detection.

    Returns the structured analysis result (status, violations, witnesses)
    that :func:`emit_proof_artifact` binds to the canonical schema.
    """
    policy = policy or default_policy()

    entity_ids, reasons = resolve_entities(events, policy)

    violations: List[Dict[str, Any]] = []
    for i, ev in enumerate(events):
        for v in policy.event_violations(ev):
            violations.append(
                {"event_index": i, "ts": ev.ts, "action": ev.action, "scope": ev.scope.realm, **v}
            )

    # Bounded congruence leak: an HSM nonce-stream observed outside fog/HSM realms.
    stream: Optional[NonceStream] = None
    for i, ev in enumerate(events):
        ns = (ev.evidence or {}).get("nonce_stream")
        if isinstance(ns, dict) and all(k in ns for k in ("base", "delta", "m")):
            stream = NonceStream(
                base=int(ns["base"]),
                delta=int(ns["delta"]),
                m=int(ns["m"]),
                max_steps=int(ns.get("max_steps", max_steps)),
            )
        observed = (ev.evidence or {}).get("nonce_observed")
        if stream is not None and observed is not None:
            x = int(observed)
            k = stream.steps_to(x)
            if k is not None and (
                ev.scope.realm.lower() in ("adtech", "institution", "cloud")
                or policy.is_ad_realm(ev.scope.realm)
            ):
                violations.append(
                    {
                        "event_index": i,
                        "ts": ev.ts,
                        "action": ev.action,
                        "scope": ev.scope.realm,
                        "kind": "NONCE_STREAM_LEAK",
                        "details": {"steps": k, "bucket": _log_bucket(max(1, k)), "observed": x},
                    }
                )

    counterexample: List[Dict[str, Any]] = []
    if violations:
        first = min(v["event_index"] for v in violations)
        for idx in range(max(0, first - 2), min(len(events), first + 1)):
            ev = events[idx]
            counterexample.append(
                {
                    "event_index": idx,
                    "ts": ev.ts,
                    "actor": ev.actor,
                    "action": ev.action,
                    "scope": {
                        "device": ev.scope.device,
                        "app": ev.scope.app,
                        "realm": ev.scope.realm,
                        "jurisdiction": ev.scope.jurisdiction,
                    },
                    "primes": ev.primes,
                    "attrs_keys": sorted((ev.attrs or {}).keys()),
                    "evidence_keys": sorted((ev.evidence or {}).keys()),
                }
            )

    status = "PROVED" if not violations else "VIOLATION"
    return {
        "status": status,
        "violations": violations,
        "counterexample": counterexample,
        "entity_ids": entity_ids,
        "edge_reasons": {
            f"{a}->{b}": {"kind": r.kind, "match_key": r.match_key}
            for (a, b), r in reasons.items()
        },
        "event_count": len(events),
        "events_sha256": sha256_hex(events_bytes) if events_bytes is not None else None,
        "policy_sha256": sha256_hex(policy_bytes) if policy_bytes is not None else None,
    }


def emit_proof_artifact(analysis: Dict[str, Any], *, artifact_id: str) -> Dict[str, Any]:
    """Bind an :func:`analyze_trace` result to the CANONICAL proof-artifact schema.

    Canonical schema: ``schemas/proof-artifact.schema.json`` (Trust-First Proof
    Artifact, v0.1) -- richer than the toy reference schema.

    Toy -> canonical mapping decisions:

      * toy ``status``          -> canonical ``result`` (identity map of the
                                   shared {PROVED,VIOLATION,INCONCLUSIVE} enum)
      * toy free-text ``claim`` -> canonical ``claim.kind = "ifc_no_flow"`` with
                                   structured ``params`` (sensitive primes must
                                   not flow into ad realms)
      * toy ``domains``         -> canonical constrained ``domains`` enum:
                                   POLICY(prime_veto)/ER -> "labels","capabilities";
                                   CONGRUENCE(mod_stream) -> "congruence"
      * toy ``inputs.events_sha256`` -> canonical ``inputs_hash`` ("sha256:...")
      * toy ``precision.mode="Toy"`` -> canonical ``precision.mode="Exact"``
                                   (the policy/congruence checks are exact, not
                                   abstract-interpretation approximations)

    Required-by-result invariants are satisfied: PROVED carries ``telemetry``,
    VIOLATION/INCONCLUSIVE carry ``witness_or_counterexample``.
    """
    result = _STATUS_TO_RESULT[analysis["status"]]

    events_sha = analysis.get("events_sha256") or sha256_hex(b"")
    inputs_hash = f"sha256:{events_sha}"
    policy_sha = analysis.get("policy_sha256") or sha256_hex(b"")

    artifact: Dict[str, Any] = {
        "schema_version": "0.1",
        "artifact_id": artifact_id,
        "producer_boundary": PRODUCER_BOUNDARY,
        "claim": {
            "kind": CLAIM_KIND,
            "params": {
                "sensitive_primes": ["PATIENT", "PARENT", "CITIZEN"],
                "forbidden_target_realms": ["adtech", "ads", "marketing", "track"],
                "statement": "sensitive identity primes do not flow into ad realms",
            },
        },
        "assumptions": {
            "coverage": ["fog_device_events"],
            # TODO: bind real event integrity once the evidence spine signs the
            # Event-IR window. The toy trace is self-reported.
            "event_integrity": "best_effort",
            "scope_integrity": "self_reported",
            "clock_model": "wall_clock_iso8601",
            "missing_evidence": [],
        },
        "policy_bundle": {
            "hash": f"sha256:{policy_sha}",
            # TODO(cosign): sign the policy bundle. Consistent with how the repo
            # defers artifact signing elsewhere -- no real signing in this kernel.
            "sig": "UNSIGNED",
        },
        "compiler_id": COMPILER_ID,
        # Constrained-enum domains. The reference's ER + policy veto operate over
        # label/capability lattices; the nonce-stream check is a congruence domain.
        "domains": ["labels", "capabilities", "congruence"],
        "budgets": {
            "max_iters": max(1, analysis.get("event_count", 1)),
            "max_time_ms": 60000,
            "max_branches": 0,
        },
        "inputs_hash": inputs_hash,
        "result": result,
        "precision": {"mode": "Exact"},
        "telemetry": {
            "event_count": analysis.get("event_count", 0),
            "entity_ids": analysis.get("entity_ids", []),
            "edge_reasons": analysis.get("edge_reasons", {}),
            "violation_count": len(analysis.get("violations", [])),
        },
        # TODO(cosign): top-level detached signature over the canonical artifact.
        "notes": (
            "Promoted from identity_is_prime_reference (prime_er). "
            "surface343, naming_projection, and the recommendation loop are out "
            "of scope and intentionally deferred."
        ),
    }

    if result in ("VIOLATION", "INCONCLUSIVE"):
        artifact["witness_or_counterexample"] = {
            "violations": analysis.get("violations", []),
            "counterexample": analysis.get("counterexample", []),
        }

    return artifact


def run(events_text: str, *, artifact_id: str = "identity-prime-michael-0001") -> Dict[str, Any]:
    """End-to-end: parse JSONL Event-IR, analyze, emit canonical artifact."""
    events = load_events_jsonl(events_text)
    policy = default_policy()
    policy_bytes = json.dumps(
        {
            "forbidden_prime_pairs": [sorted(p) for p in (frozenset(["PATIENT", "ADS"]),
                                                          frozenset(["PARENT", "ADS"]),
                                                          frozenset(["CITIZEN", "ADS"]))],
        },
        sort_keys=True,
    ).encode("utf-8")
    analysis = analyze_trace(
        events,
        policy,
        events_bytes=events_text.encode("utf-8"),
        policy_bytes=policy_bytes,
    )
    return emit_proof_artifact(analysis, artifact_id=artifact_id)
