"""The vendored DeviceService contract: profile digesting, reading construction, and the
hermetic fail-closed validation gate.

Schema provenance (vendored so validation needs no network and no spec checkout):
    repo    SourceOS-Linux/sourceos-spec  (PR #215, feat/device-service-contract)
    paths   schemas/DeviceProfile.json, schemas/DeviceReading.json,
            schemas/NullAbsenceRecord.json
    commit  ba84bed8d7826d9c52ed55dd0d176bf853e43631
            (2026-07-29, "schemas: DeviceService contract v0.1 — the southbound
            device plane (W8.7)"; NullAbsenceRecord is unchanged from 487e4b6, the
            MPCC event contract — it is REUSED, not re-invented)
    sha256  DeviceProfile.json     2d68700fe5f33b7955bd086125f384b27000aeeafd866504dd5bf7b46d51ff28
            DeviceReading.json     261f1972cb16e3468e2b2eb6204748005f1c10c4dd9fb35e5dcba3a3cc6119df
            NullAbsenceRecord.json 9e51c264acec89efc8021e62e54e2e513e9890e85126f46f11ecf93a9936f84d
Re-vendor by copying the files from sourceos-spec and updating this block. The sha256s
are asserted at import: a drifted or hand-edited copy fails LOUDLY at startup, never
silently at emit time — this service's whole claim is "what enters the log conforms to
the estate contract", so the contract itself must be tamper-evident.
(apps/market-replay/src/market_replay/contract.py and apps/nugget-extractor precedent.)

THE NORMATIVE INVARIANT this module enforces: a reading is ATTRIBUTABLE OR IT IS
NOTHING. Beyond schema conformance, every reading is checked against the profile it
cites — metric declared, unit and source address equal to the declaration, value of the
declared type and inside the declared range, digest equal to the RECOMPUTED digest of
the profile as loaded. An unattributable reading is not emitted, it is counted.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

SPEC_VERSION = "0.1.0"

PROFILE_SCHEMA_SHA256 = "2d68700fe5f33b7955bd086125f384b27000aeeafd866504dd5bf7b46d51ff28"
READING_SCHEMA_SHA256 = "261f1972cb16e3468e2b2eb6204748005f1c10c4dd9fb35e5dcba3a3cc6119df"
ABSENCE_SCHEMA_SHA256 = "9e51c264acec89efc8021e62e54e2e513e9890e85126f46f11ecf93a9936f84d"

# KKO reference concepts, taken from the TBox this estate actually vendors
# (apps/owl-reasoner/src/owl_reasoner/data/kko-2.10.n3, namespace
# http://kbpedia.org/ontologies/kko#). BOTH terms were verified present in that file —
# they are not invented URIs, and tests/test_kko.py re-verifies it against the vendored
# TBox so an invented URI cannot survive CI.
#
# They are deliberately COARSE. KKO is the 169-term upper ontology; the ~58k KBpedia
# reference-concept layer that would carry a concept as specific as "temperature" is NOT
# vendored anywhere in this estate. Citing kbpedia.org/kko/rc/Temperature would look more
# precise and resolve to nothing — the same silent-wrong this service exists to prevent.
# The metric name and unit carry the specificity the ontology cannot. As in
# nugget-extractor: these are DECLARED type refs; nothing here resolves them against a
# loaded KKO (the platform-wide TBox binding is a separate, tracked gap).
KKO = "http://kbpedia.org/ontologies/kko#"
KKO_QUANTITY = KKO + "Quantity"  # a magnitude-with-unit (number/integer metrics)
KKO_STATES = KKO + "States"      # a state of a thing (boolean metrics)


def _load(name: str, pinned: str) -> tuple[dict[str, Any], bytes]:
    raw = (resources.files("device_service") / "schemas" / name).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != pinned:  # tamper-evident vendoring — see module docstring
        raise RuntimeError(
            f"vendored {name} drifted: sha256 {actual} != pinned {pinned}; "
            "re-vendor from sourceos-spec and update contract.py provenance"
        )
    return json.loads(raw), raw


PROFILE_SCHEMA, _PROFILE_BYTES = _load("DeviceProfile.json", PROFILE_SCHEMA_SHA256)
READING_SCHEMA, _READING_BYTES = _load("DeviceReading.json", READING_SCHEMA_SHA256)
ABSENCE_SCHEMA, _ABSENCE_BYTES = _load("NullAbsenceRecord.json", ABSENCE_SCHEMA_SHA256)

# jsonschema treats `format` as an ANNOTATION unless a checker is supplied, so a plain
# Draft202012Validator(SCHEMA) never validates the schema's "format": "date-time" — a
# structurally-valid reading carrying "not-a-timestamp" would pass the gate this module
# describes as fail-closed. Passing the checker is not sufficient on its own: its
# date-time entry only exists when rfc3339-validator is installed, so a missing
# dependency would turn the fix back into the no-op it replaces, silently, and only in
# whichever environment lacked the package. The assertion makes that impossible: no
# timestamp checking means no import. (market-replay found this the hard way.)
_FORMAT_CHECKER = Draft202012Validator.FORMAT_CHECKER
if "date-time" not in _FORMAT_CHECKER.checkers:  # pragma: no cover - guarded by test
    raise RuntimeError(
        "jsonschema's date-time format checker is unavailable (install rfc3339-validator). "
        "Refusing to start: this module claims per-reading schema validation, and without "
        "it every `format: date-time` in DeviceReading.json would go unchecked."
    )

PROFILE_VALIDATOR = Draft202012Validator(PROFILE_SCHEMA, format_checker=_FORMAT_CHECKER)
READING_VALIDATOR = Draft202012Validator(READING_SCHEMA, format_checker=_FORMAT_CHECKER)
ABSENCE_VALIDATOR = Draft202012Validator(ABSENCE_SCHEMA, format_checker=_FORMAT_CHECKER)

# The absence kinds a southbound driver can honestly attribute. A driver knows the
# device did not answer (timeout), that the link broke (transport_failure), or that it
# has no basis to say which (no_event_observed). It does NOT know that a device chose
# silence, refused, or was redacted — those are claims about intent, and a driver
# asserting them would be inventing a cause. The full 12-kind taxonomy stays available
# to producers that can actually attribute; this service restricts itself to what it
# can know.
DRIVER_ABSENCE_KINDS = ("timeout", "transport_failure", "no_event_observed")

# Normative digest projection — MUST stay byte-identical to
# sourceos-spec tools/validate_device_service_examples.py DIGEST_FIELDS. Exactly the
# fields that decide which readings are admissible; prose, labels and timestamps are
# excluded so a documentation edit does not orphan live readings.
DIGEST_FIELDS = ["deviceClass", "protocol", "metrics"]

SIMULATED_LABEL = "synthetic:simulated-device"
SIMULATED_RISK = "not-a-measurement"


class ContractError(ValueError):
    """A reading (or profile) is not admissible. Never swallowed: counted and logged."""


def definition_digest(profile: dict[str, Any]) -> str:
    """Recompute DeviceProfile.definitionDigest. Normative: sha256 over the canonical
    JSON (sorted keys, no whitespace, UTF-8) of the DIGEST_FIELDS projection of the
    document AS WRITTEN — schema defaults are not materialised, so an omitted field and
    an explicitly-defaulted one are different declarations and hash differently."""
    core = {field: profile[field] for field in DIGEST_FIELDS}
    canonical = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def instant(value: str) -> datetime | None:
    """Parse an RFC3339 `date-time` to an absolute instant, or None if it is not one.

    MUST stay behaviourally identical to sourceos-spec
    tools/validate_device_service_examples.py instant() — the spec tool and this gate
    have to agree on what "receivedAt >= observedAt" means, or a reading the estate
    conformance tool refuses would still be emitted here.

    Comparing these as STRINGS is wrong and silently so: DeviceReading pins
    `format: date-time` with NO `pattern`, so schema-valid values vary in both UTC
    offset and fractional-second precision. Two proven counterexamples the string
    compare misses (tests/test_contract.py holds both):

        observedAt 2026-07-29T09:15:00.500Z / receivedAt 2026-07-29T09:15:00Z
            receivedAt is 500ms EARLIER, but '.' (0x2E) < 'Z' (0x5A), so it sorts later;
        observedAt 2026-07-29T20:00:00+00:00 / receivedAt 2026-07-29T21:00:00+05:00
            receivedAt is 4h EARLIER, but "21" > "20" lexicographically.

    An ordering check built on string compare is a check that cannot fail for exactly
    the documents most likely to be wrong. Normative in specs/device-service-contract.md
    §6: the ordering is over instants, not strings.
    """
    text = value.strip()
    if len(text) > 10 and text[10] in "tT":  # RFC3339 permits a lowercase separator
        text = text[:10] + "T" + text[11:]
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # RFC3339 requires an offset. A naive stamp is not an instant; refuse it rather
        # than assume UTC and compare two different clocks.
        return None
    return parsed.astimezone(timezone.utc)


def load_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate a profile and RECOMPUTE its digest. A profile whose stored digest is not
    the digest of its own declared capability is refused at load: every reading pins that
    value, so admitting a lying digest would make every downstream pin meaningless."""
    errors = sorted(PROFILE_VALIDATOR.iter_errors(raw), key=str)
    if errors:
        raise ContractError(f"profile does not conform: {errors[0].message}")
    recomputed = definition_digest(raw)
    if raw["definitionDigest"] != recomputed:
        raise ContractError(
            f"profile {raw['id']}: definitionDigest {raw['definitionDigest']} is not the "
            f"digest of its own declared capability (recomputed {recomputed})"
        )
    names = [m["metric"] for m in raw["metrics"]]
    if len(names) != len(set(names)):
        raise ContractError(f"profile {raw['id']}: duplicate metric names {names}")
    return raw


def metric_of(profile: dict[str, Any], metric: str) -> dict[str, Any]:
    for declared in profile["metrics"]:
        if declared["metric"] == metric:
            return declared
    raise ContractError(f"metric {metric!r} is not declared by {profile['id']}")


def is_simulated(profile: dict[str, Any]) -> bool:
    return profile["protocol"] == "virtual"


def build_reading(
    *,
    profile: dict[str, Any],
    device_ref: str,
    metric: str,
    value: Any,
    quality: str,
    observed_at: str,
    received_at: str,
    wall_time: str,
    logical_time: int,
    sequence_ref: int,
    workspace_ref: str,
    branch_ref: str,
    actor_ref: str,
    raw_payload: Any = None,
    quality_flags: list[str] | None = None,
    null_absence_ref: str | None = None,
    causal_parents: list[str] | None = None,
) -> dict[str, Any]:
    """Construct one DeviceReading from a driver sample and its profile.

    Everything that makes the reading attributable is copied FROM THE PROFILE — unit,
    source address, ontology type, digest — so a driver cannot supply them and cannot
    get them wrong. A driver reports a value; the contract layer says what it means.
    """
    declared = metric_of(profile, metric)
    simulated = is_simulated(profile)
    reading: dict[str, Any] = {
        "id": f"urn:srcos:device-reading:{reading_local_id(device_ref, metric, sequence_ref)}",
        "type": "DeviceReading",
        "specVersion": SPEC_VERSION,
        "actorRef": actor_ref,
        "workspaceRef": workspace_ref,
        "branchRef": branch_ref,
        "visibilityScope": ["private"],
        "wallTime": wall_time,
        "logicalTime": logical_time,
        "causalParents": causal_parents or [],
        "provenanceLinks": [
            # Stated, not merely checkable: the attribution must survive being read by
            # something that never loads the profile.
            {"rel": "declared_by", "ref": profile["id"]},
            {"rel": "produced_by", "ref": device_ref},
            {"rel": "ingested_by", "ref": "prophet-platform:apps/device-service"},
        ],
        # A simulated reading carries the not-a-measurement labels its profile carries.
        # This is the KnowledgeNugget model-generated rule applied to sensors: generated
        # data that is indistinguishable downstream is worse than no data, because it is
        # believed. The labels ride on the reading itself, not only on the profile a
        # consumer might not fetch.
        "policyLabels": [SIMULATED_LABEL] if simulated else list(profile.get("policyLabels", [])),
        "riskLabels": [SIMULATED_RISK] if simulated else list(profile.get("riskLabels", [])),
        "deviceRef": device_ref,
        "deviceProfileRef": profile["id"],
        "profileDigest": profile["definitionDigest"],
        "metric": metric,
        "sourceAddress": declared["sourceAddress"],
        "value": value,
        "unit": declared["unit"],
        "quality": quality,
        "observedAt": observed_at,
        "receivedAt": received_at,
        "sequenceRef": sequence_ref,
        "nullAbsenceRef": null_absence_ref,
        "qualityFlags": quality_flags or [],
        "rawPayload": raw_payload,
    }
    if declared.get("kkoTypeRef"):
        reading["kkoTypeRef"] = declared["kkoTypeRef"]
    return reading


def reading_local_id(device_ref: str, metric: str, sequence_ref: int) -> str:
    """Deterministic local id: the same (device, metric, seq) always yields the same URN,
    so a restart re-emitting a batch upserts the same node instead of minting a duplicate.
    The URN charset is [A-Za-z0-9._~-]; device slugs and dotted metric names are safe, the
    urn: prefix and its colons are not, so only the device's local part is used."""
    device_slug = device_ref.rsplit(":", 1)[-1]
    return f"{device_slug}-{metric}-{sequence_ref:012d}"


def validate_reading(reading: dict[str, Any], profile: dict[str, Any]) -> None:
    """THE fail-closed gate. Two layers, both mandatory:

    1. schema conformance against the vendored DeviceReading.json;
    2. ATTRIBUTION against the profile the reading cites — the layer a schema cannot
       express, because it is a claim about two documents agreeing.

    Raises ContractError on any non-conformance. The caller does not emit and does not
    count the reading as emitted; it counts the failure.
    """
    errors = sorted(READING_VALIDATOR.iter_errors(reading), key=str)
    if errors:
        raise ContractError(f"schema: {errors[0].message}")

    if reading["deviceProfileRef"] != profile["id"]:
        raise ContractError(
            f"reading cites {reading['deviceProfileRef']} but was validated against {profile['id']}"
        )
    recomputed = definition_digest(profile)
    if reading["profileDigest"] != recomputed:
        raise ContractError(
            f"profileDigest {reading['profileDigest']} != the recomputed digest of "
            f"{profile['id']} ({recomputed}) — the reading names a revision it was not "
            f"admitted against"
        )

    declared = metric_of(profile, reading["metric"])
    if reading["unit"] != declared["unit"]:
        raise ContractError(
            f"unit {reading['unit']!r} contradicts the declared {declared['unit']!r} "
            f"for {reading['metric']}"
        )
    if reading["sourceAddress"] != declared["sourceAddress"]:
        raise ContractError(
            f"sourceAddress {reading['sourceAddress']!r} is not the channel declared for "
            f"{reading['metric']} ({declared['sourceAddress']!r})"
        )
    if declared.get("kkoTypeRef") and reading.get("kkoTypeRef") != declared["kkoTypeRef"]:
        raise ContractError(f"kkoTypeRef disagrees with the declaration for {reading['metric']}")

    # Compare INSTANTS, never strings (see instant()). The schema's date-time format
    # checker is the first line and rejects most malformed stamps, but it does not make
    # two well-formed stamps comparable — that is this parse. An unorderable pair is
    # refused rather than waved through: a check that cannot be performed has not passed.
    # Copilot #1069: `if received:` treated '' as absent and skipped the gate. The
    # whole point of this PR is that malformed timestamps must fail closed, not
    # slip through under the same truthiness check that admitted the good ones.
    # Explicit presence check; let instant('') drive the fail-closed refusal.
    received = reading.get("receivedAt")
    if received is not None:
        observed_at, received_at = instant(reading["observedAt"]), instant(received)
        if observed_at is None or received_at is None:
            raise ContractError(
                f"observedAt/receivedAt must be RFC3339 instants with an offset "
                f"({reading['observedAt']!r} -> {received!r}) — an unorderable pair "
                f"cannot be checked, so the reading is not admissible"
            )
        if received_at < observed_at:
            raise ContractError(
                f"receivedAt precedes observedAt by "
                f"{(observed_at - received_at).total_seconds()}s — the reading arrived "
                f"before it was observed"
            )

    simulated = is_simulated(profile)
    labelled = SIMULATED_LABEL in reading["policyLabels"]
    if simulated and not labelled:
        raise ContractError(
            f"produced under a virtual profile but carries no {SIMULATED_LABEL!r} label — "
            "simulated data must stay visibly distinguishable downstream"
        )
    if labelled and not simulated:
        raise ContractError("a physically-measured reading must not be labelled simulated")

    if reading["quality"] == "unavailable":
        # The schema already binds value:null + a present nullAbsenceRef; this is the
        # non-null check the schema's `not` covers, restated where the error is legible.
        if not reading.get("nullAbsenceRef"):
            raise ContractError("unavailable reading carries no nullAbsenceRef")
        return

    expected = declared["valueType"]
    value = reading["value"]
    ok = {
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "string": isinstance(value, str),
    }[expected]
    if not ok:
        raise ContractError(
            f"value {value!r} is not the declared {expected} for {reading['metric']}"
        )
    if expected in ("number", "integer"):
        lo, hi = declared["minimum"], declared["maximum"]
        if not (lo <= value <= hi):
            raise ContractError(
                f"value {value!r} is outside the declared operating range [{lo}, {hi}] for "
                f"{reading['metric']} — a device disagreeing with its own profile is a "
                f"fault or a wrong profile, never a datum to pass through quietly"
            )


def flatten(reading: dict[str, Any], ingest_time: str) -> dict[str, Any]:
    """The graph-node property projection: flat scalars for querying, PLUS the full
    validated reading as canonical JSON — so the log carries the spec-conformant OBJECT,
    not just a lossy projection. (market-replay / nugget-extractor precedent.)"""
    return {
        "readingId": reading["id"],
        "deviceRef": reading["deviceRef"],
        "deviceProfileRef": reading["deviceProfileRef"],
        "profileDigest": reading["profileDigest"],
        "metric": reading["metric"],
        "sourceAddress": reading["sourceAddress"],
        "unit": reading["unit"],
        "quality": reading["quality"],
        "valueNum": reading["value"] if isinstance(reading["value"], (int, float))
        and not isinstance(reading["value"], bool) else None,
        "valueBool": reading["value"] if isinstance(reading["value"], bool) else None,
        "valueStr": reading["value"] if isinstance(reading["value"], str) else None,
        "observedAt": reading["observedAt"],
        "receivedAt": reading["receivedAt"],
        "wallTime": reading["wallTime"],
        "logicalTime": reading["logicalTime"],
        "sequenceRef": reading["sequenceRef"],
        "simulated": SIMULATED_LABEL in reading["policyLabels"],
        "specVersion": reading["specVersion"],
        "ingestTime": ingest_time,
        "reading": json.dumps(reading, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
    }


def batch_hash(readings: list[dict[str, Any]]) -> str:
    """sha256 over the canonical JSON of the batch, in emission order. This is what the
    sealed receipt binds: change any byte of any reading and the receipt no longer
    matches the batch it claims to cover."""
    canonical = json.dumps(readings, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def startup_check(profiles: list[dict[str, Any]]) -> None:
    """Boot-time fail-closed gate: both schemas are valid 2020-12 documents, every
    commissioned profile conforms AND carries its own recomputed digest, and a probe
    reading built by THIS code against each profile's first metric validates. Any drift
    dies here, before the first poll — a visible crash, never a silently dead loop
    behind a green pod."""
    Draft202012Validator.check_schema(PROFILE_SCHEMA)
    Draft202012Validator.check_schema(READING_SCHEMA)
    for profile in profiles:
        load_profile(profile)
        declared = profile["metrics"][0]
        probe_value = {
            "number": float(declared.get("minimum") or 0),
            "integer": int(declared.get("minimum") or 0),
            "boolean": False,
            "string": "probe",
        }[declared["valueType"]]
        reading = build_reading(
            profile=profile,
            device_ref="urn:srcos:device:startup_probe",
            metric=declared["metric"],
            value=probe_value,
            quality="ok",
            observed_at="2026-01-01T00:00:00.000Z",
            received_at="2026-01-01T00:00:00.000Z",
            wall_time="2026-01-01T00:00:00.000Z",
            logical_time=0,
            sequence_ref=0,
            workspace_ref="urn:srcos:workspace:startup_probe",
            branch_ref="urn:srcos:branch:startup_probe",
            actor_ref="urn:srcos:agent:device_service",
            raw_payload={"probe": True},
        )
        validate_reading(reading, profile)


def build_absence_record(
    *,
    reading_id: str,
    kind: str,
    observed_at: str,
    workspace_ref: str,
    branch_ref: str,
    device_ref: str,
    metric: str,
    expected_next_sequence: int,
    causal_notes: str,
) -> dict[str, Any]:
    """Type the absence, rather than re-reporting a stale value as if it were measured.

    The record reuses the existing 12-kind MPCC taxonomy — the device plane does not get
    its own vocabulary — and this service restricts itself to the three kinds a driver
    can honestly attribute (DRIVER_ABSENCE_KINDS).
    """
    if kind not in DRIVER_ABSENCE_KINDS:
        raise ContractError(
            f"absence kind {kind!r} is not one a southbound driver can attribute "
            f"{list(DRIVER_ABSENCE_KINDS)} — asserting intent the driver cannot observe"
        )
    return {
        "id": f"urn:srcos:null-absence:{reading_id.rsplit(':', 1)[-1]}",
        "type": "NullAbsenceRecord",
        "specVersion": SPEC_VERSION,
        "kind": kind,
        "observedAt": observed_at,
        "relatedEventRef": reading_id,
        "relatedBranchRef": branch_ref,
        "relatedWorkspaceRef": workspace_ref,
        "causalNotes": causal_notes,
        "policyLabels": [],
        "provenanceLinks": [
            {"rel": "detected_by", "ref": "prophet-platform:apps/device-service"},
            {"rel": "produced_by", "ref": device_ref},
        ],
        "details": {"metric": metric, "expectedNextSequence": expected_next_sequence},
    }


def validate_absence_record(record: dict[str, Any], reading: dict[str, Any]) -> None:
    """Schema conformance plus the back-reference: an absence record that does not point
    at the reading it explains leaves the reading's nullAbsenceRef dangling."""
    errors = sorted(ABSENCE_VALIDATOR.iter_errors(record), key=str)
    if errors:
        raise ContractError(f"absence schema: {errors[0].message}")
    if record["relatedEventRef"] != reading["id"]:
        raise ContractError("absence record does not point back at the reading it explains")
    if reading.get("nullAbsenceRef") != record["id"]:
        raise ContractError("reading's nullAbsenceRef does not name this absence record")
