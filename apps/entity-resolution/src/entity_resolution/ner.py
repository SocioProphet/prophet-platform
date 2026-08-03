"""NER (mention/span) extraction — the ``extract -> mentions`` head of the
identity spine that entity-resolution previously lacked.

The resolver turns records into proof-carrying entities, but something has to
produce the mentions/records first. This is the local-first extraction phase from
the ER/NER integration plan: lightweight, deterministic, dictionary + pattern NER
for high-value entity types, emitting a MentionSet that conforms to
regis-entity-graph ``schemas/ner/mention.schema.json`` (v0.1).

Design choices from the plan:

* Overlapping / multi-labelled spans are first-class — a phrase may be at once a
  named entity, a prime-topic marker, and a policy-sensitive context cue.
* Immediate PII minimization: high-risk classes (CREDENTIAL, TRACKING_IDENTIFIER,
  and IDENTIFIER surfaces that look like secrets) are hashed on the span. FIPS:
  SHA-256 is authoritative.
* The extraction is stamped with the ``locality`` scope it ran in.

Pure-stdlib so it stays trivially testable and runs local-first (on device / in
citizen-fog) with no model download.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

SCHEMA_VERSION = "regis.ner.mention_set.v0.1"
EXTRACTOR_VERSION = "regis-ner-deterministic@0.1.0"

# Kept in sync with regis-entity-graph schemas/ner/entity-class.schema.json.
BASE_CLASSES = {
    "PERSON", "ORG", "PRODUCT_SERVICE", "DEVICE", "ACCOUNT", "IDENTIFIER",
    "CREDENTIAL", "LOCATION", "JURISDICTION", "CONSENT_ARTIFACT", "POLICY_TERM",
    "PRIME_TOPIC_MENTION", "ACTION_EVENT_TRIGGER", "RELATIONSHIP_MENTION",
}
DOMAIN_CLASSES = {
    "SCOPE_REALM", "TRACKING_IDENTIFIER", "HSM_HANDLE", "NONCE_STREAM",
    "EXPORT_ATTEMPT", "CONSENT_WITNESS", "SENSITIVE_CONTEXT", "CHILD_CONTEXT",
    "PATIENT_CONTEXT", "CIVIC_CONTEXT", "MARKETING_CONTEXT",
}
ENTITY_CLASSES = BASE_CLASSES | DOMAIN_CLASSES

LOCALITIES = {"CITIZEN_FOG", "CITIZEN_CLOUD", "INSTITUTION", "ADTECH", "HSM"}
SOURCE_TYPES = {"document", "form", "log", "network_event", "message", "page"}

# Classes whose surface value is a secret/identifier and must be minimized (hashed).
PII_MINIMIZE = {"CREDENTIAL", "TRACKING_IDENTIFIER", "HSM_HANDLE", "NONCE_STREAM"}

# Deterministic high-value patterns. Each entry: (regex, entity_class, secondary_classes, confidence).
_PATTERNS: list[tuple[re.Pattern[str], str, tuple[str, ...], float]] = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "IDENTIFIER", ("ACCOUNT",), 0.97),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "IDENTIFIER", ("SENSITIVE_CONTEXT",), 0.95),
    (re.compile(r"\b(?:tid|trk|track|gaid|idfa)[-_][A-Za-z0-9]{6,}\b", re.I), "TRACKING_IDENTIFIER", ("MARKETING_CONTEXT",), 0.93),
    (re.compile(r"\b(?:sk|pk|tok|bearer|apikey)[-_][A-Za-z0-9]{8,}\b", re.I), "CREDENTIAL", ("SENSITIVE_CONTEXT",), 0.9),
    (re.compile(r"\bhsm://[A-Za-z0-9/_-]+\b"), "HSM_HANDLE", (), 0.9),
]

# Context-cue dictionary — words that mark a policy-sensitive context. These deliberately
# OVERLAP any entity spans they sit inside (the plan's overlapping-span requirement).
_CONTEXT_CUES: list[tuple[re.Pattern[str], str, tuple[str, ...]]] = [
    (re.compile(r"\b(?:pediatric|paediatric|child|minor|kid|infant)\b", re.I), "CHILD_CONTEXT", ()),
    (re.compile(r"\b(?:patient|clinic|clinical|hospital|ward|diagnosis|medical)\b", re.I), "PATIENT_CONTEXT", ("SENSITIVE_CONTEXT",)),
    (re.compile(r"\b(?:vote|voter|ballot|election|civic|census)\b", re.I), "CIVIC_CONTEXT", ()),
    (re.compile(r"\b(?:consent|opt-?in|opt-?out|authoriz\w+)\b", re.I), "CONSENT_ARTIFACT", ()),
    (re.compile(r"\b(?:ad|ads|advert\w*|campaign|retarget\w*)\b", re.I), "MARKETING_CONTEXT", ()),
]


def sha256_hex(value: str) -> str:
    """FIPS: SHA-256 is the authoritative digest for minimized PII surfaces."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mk_pii(text: str) -> dict[str, Any]:
    return {"minimized": True, "hash_alg": "SHA-256", "value_hash": sha256_hex(text)}


def extract_mentions(
    text: str,
    *,
    source_id: str,
    source_type: str = "document",
    locality: str = "CITIZEN_FOG",
    event_ir_id: str | None = None,
    gazetteer: dict[str, str] | None = None,
    scope_realm: str = "FOG",
) -> dict[str, Any]:
    """Extract a regis-conformant MentionSet from ``text``.

    ``gazetteer`` maps a surface form -> entity_class (e.g. {"Mercy General": "ORG"})
    for dictionary NER of known high-value entities. Pattern NER covers identifiers,
    credentials, tracking ids and HSM handles deterministically. Context cues are
    added as OVERLAPPING mentions so downstream disambiguation sees them.
    """
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unknown source_type {source_type}")
    if locality not in LOCALITIES:
        raise ValueError(f"unknown locality {locality}")

    mentions: list[dict[str, Any]] = []
    counter = 0

    def add(start: int, end: int, klass: str, secondary: tuple[str, ...], conf: float) -> None:
        nonlocal counter
        counter += 1
        surface = text[start:end]
        m: dict[str, Any] = {
            "mention_id": f"m{counter}",
            "span": {"start": start, "end": end, "text": surface},
            "entity_class": klass,
            "confidence": round(conf, 4),
            "scope_realm": scope_realm,
            "provenance": {
                "source_event_ids": [event_ir_id] if event_ir_id else [],
                "artifact_ids": [],
            },
        }
        secondary_clean = [c for c in secondary if c != klass]
        if secondary_clean:
            m["secondary_classes"] = sorted(set(secondary_clean))
        if klass in PII_MINIMIZE:
            m["pii"] = _mk_pii(surface)
        mentions.append(m)

    # 1. Deterministic pattern NER (identifiers / credentials / trackers).
    for pat, klass, secondary, conf in _PATTERNS:
        for match in pat.finditer(text):
            add(match.start(), match.end(), klass, secondary, conf)

    # 2. Dictionary NER over the gazetteer (case-insensitive, all occurrences).
    for surface, klass in (gazetteer or {}).items():
        if klass not in ENTITY_CLASSES:
            raise ValueError(f"gazetteer maps to unknown entity_class {klass}")
        for match in re.finditer(re.escape(surface), text, flags=re.I):
            add(match.start(), match.end(), klass, (), 0.85)

    # 3. Context cues — emitted as overlapping mentions.
    for pat, klass, secondary, in ((p, k, s) for p, k, s in _CONTEXT_CUES):
        for match in pat.finditer(text):
            add(match.start(), match.end(), klass, secondary, 0.8)

    mentions.sort(key=lambda m: (m["span"]["start"], m["span"]["end"], m["entity_class"]))
    # Re-number after the sort so ids are stable/positional.
    for i, m in enumerate(mentions, start=1):
        m["mention_id"] = f"m{i}"

    return {
        "schema_version": SCHEMA_VERSION,
        "source_ref": {
            "source_id": source_id,
            "source_type": source_type,
            **({"event_ir_id": event_ir_id} if event_ir_id else {}),
        },
        "locality": locality,
        "extractor_version": EXTRACTOR_VERSION,
        "overlaps_allowed": True,
        "mentions": mentions,
    }


def mentions_to_records(mention_set: dict[str, Any]) -> list[dict[str, Any]]:
    """Bridge NER -> ER: fold PERSON/ORG mentions into resolver Record inputs so the
    same request can flow extract -> resolve. Context/identifier mentions ride along
    as attributes/primes rather than becoming their own entities."""
    records: list[dict[str, Any]] = []
    src = mention_set["source_ref"]["source_id"]
    for m in mention_set["mentions"]:
        if m["entity_class"] in ("PERSON", "ORG"):
            attrs: dict[str, str] = {}
            for other in mention_set["mentions"]:
                if other is m:
                    continue
                if other["entity_class"] in ("IDENTIFIER", "ACCOUNT") and "email" not in attrs and "@" in other["span"]["text"]:
                    attrs["email"] = other["span"]["text"].lower()
            primes = sorted({
                p
                for other in mention_set["mentions"]
                for p in other.get("prime_topic_support", [])
            })
            records.append({
                "id": f"{src}:{m['mention_id']}",
                "name": m["span"]["text"],
                "attributes": attrs,
                "scope": m.get("scope_realm", ""),
                "primes": primes,
            })
    return records
