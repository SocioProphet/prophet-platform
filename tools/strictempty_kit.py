#!/usr/bin/env python3
"""StrictEmpty kit — the Inception Framework strict-initial-object algebra (ADR-036).

Zero-dependency reference implementation of the three invariants, with property
tests runnable via `python3 tools/strictempty_kit.py --selftest`.

  I1  Genesis uniqueness : non-empty objects are minted ONLY by the genesis functor.
  I2  Iso-erase          : the only morphism X -> empty is a certified isomorphism
                            (shred to the canonical empty value + certificate).
  I3  Absorption         : prod(x, empty) == empty   and   exec_bottom(x) == empty.

These are deliberately small and pure so they can be reused as a library and as the
property-test oracle that CI runs. Real systems bind digest_empty() to the canonical
byte encoding (TritPack243 / canonical-json) per schema.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


# --- canonical empty + digest --------------------------------------------------

EMPTY = None  # the canonical empty value for the reference (schema-bound in prod)


def canonical_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest_empty() -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(EMPTY)).hexdigest()


def is_empty(value) -> bool:
    return canonical_bytes(value) == canonical_bytes(EMPTY)


# --- I3 absorption -------------------------------------------------------------

def prod(x, y):
    """Monoidal product. Emptiness absorbs: X x empty == empty."""
    if is_empty(x) or is_empty(y):
        return EMPTY
    return (x, y)


# capability lattice: bottom is strict; exec under bottom yields empty.
BOTTOM = "⊥"


def exec_under(capability, x):
    """exec_bottom(x) == empty (c x bottom == bottom)."""
    if capability == BOTTOM:
        return EMPTY
    return x


# --- I1 genesis ----------------------------------------------------------------

class GenesisError(RuntimeError):
    pass


def genesis(constructor_token: str, payload):
    """The ONLY way to mint a non-empty object from empty. A registry would record
    (digest, signer); here we just gate on a genesis token to model uniqueness."""
    if constructor_token != "genesis":
        raise GenesisError("non-empty objects may only be minted by the genesis functor")
    return payload


# --- I2 iso-erase --------------------------------------------------------------

@dataclass(frozen=True)
class EmptinessCertificate:
    pre_digest: str
    shred_digest: str
    empty_digest: str

    def check(self) -> bool:
        return self.shred_digest == self.empty_digest


def erase_iso(x):
    """Two-phase erase: shred x to the canonical empty value, then certify.
    Returns (x0, cert). Admission accepts x -> empty only if cert.check()."""
    pre = "sha256:" + hashlib.sha256(canonical_bytes(x)).hexdigest()
    x0 = EMPTY  # deterministic zero-information variant
    cert = EmptinessCertificate(
        pre_digest=pre,
        shred_digest="sha256:" + hashlib.sha256(canonical_bytes(x0)).hexdigest(),
        empty_digest=digest_empty(),
    )
    return x0, cert


# --- property tests ------------------------------------------------------------

def _selftest() -> int:
    failures = []

    # I3 absorption
    if not is_empty(prod({"a": 1}, EMPTY)):
        failures.append("I3: prod(x, empty) != empty")
    if not is_empty(prod(EMPTY, {"a": 1})):
        failures.append("I3: prod(empty, x) != empty")
    if not is_empty(exec_under(BOTTOM, {"a": 1})):
        failures.append("I3: exec_under(bottom, x) != empty")
    if is_empty(exec_under("cap:ok", {"a": 1})):
        failures.append("I3: exec_under(non-bottom, x) collapsed to empty")

    # I1 genesis uniqueness
    try:
        genesis("not-genesis", {"a": 1})
        failures.append("I1: non-genesis constructor minted a non-empty object")
    except GenesisError:
        pass
    if genesis("genesis", {"a": 1}) != {"a": 1}:
        failures.append("I1: genesis functor failed to mint")

    # I2 iso-erase
    x0, cert = erase_iso({"secret": "x"})
    if not is_empty(x0):
        failures.append("I2: erase_iso did not reach empty")
    if not cert.check():
        failures.append("I2: certificate did not verify shred_digest == empty_digest")

    # I2 negative: a forged cert whose shred != empty must fail check()
    forged = EmptinessCertificate(pre_digest="sha256:dead", shred_digest="sha256:beef",
                                  empty_digest=digest_empty())
    if forged.check():
        failures.append("I2: forged certificate (shred != empty) verified")

    if failures:
        print("STRICTEMPTY SELFTEST: FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("STRICTEMPTY SELFTEST: PASS (I1 genesis, I2 iso-erase, I3 absorption)")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
