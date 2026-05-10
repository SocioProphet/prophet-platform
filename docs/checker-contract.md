# Proof Artifact Checker Contract v0.1

Status: contract bootstrap.

The checker is the small trusted verifier for Trust-First proof artifacts. The certifier may be complex. The checker should be small, deterministic, auditable, and fail-closed.

## Responsibilities

The checker validates:

1. schema version and JSON shape;
2. policy bundle hash/signature;
3. canonical input hash;
4. coverage requirements for the claim kind;
5. verdict-specific evidence;
6. trust-root assumptions allowed by policy;
7. optional invariant or deterministic replay.

## Pseudocode

```python
def check(artifact, events, config, policy):
    assert schema_ok(artifact)
    assert schema_version_allowed(artifact.schema_version)
    assert verify_policy_bundle(artifact.policy_bundle)
    assert recompute_inputs_hash(events, config) == artifact.inputs_hash
    assert coverage_ok(artifact.claim.kind, artifact.assumptions.coverage)
    assert trust_roots_allowed(artifact.assumptions, policy)

    if artifact.result == "VIOLATION":
        assert witness_consistent(artifact.witness_or_counterexample, events)
        assert witness_violates_claim(artifact.claim, artifact.witness_or_counterexample)
        return "accepted_violation"

    if artifact.result == "PROVED":
        assert not artifact.assumptions.missing_evidence
        assert not budget_exhausted(artifact)
        if "invariant" in artifact:
            assert invariant_implies_claim(artifact.invariant, artifact.claim)
        else:
            assert deterministic_replay_ok(artifact, events, config)
        return "accepted_proof"

    if artifact.result == "INCONCLUSIVE":
        assert artifact.assumptions.missing_evidence or precision_or_budget_gap(artifact)
        return "accepted_inconclusive"

    raise Reject()
```

## Required coverage by claim kind

### kms_key_usage

Required event families:

- `Policy.Pin`
- `Identity.Attest`
- `KMS.Decrypt` or relevant KMS operation family
- `Token.Consume` when budgets are claimed
- `Data.Write`
- `Net.Send`

Missing required families block `PROVED` and should produce `INCONCLUSIVE` unless a direct violation is witnessed.

### ifc_no_flow

Required event families:

- label assignment or label-bearing payload events;
- source read events;
- sink write/send events;
- declassification events when exceptions are allowed.

### boundary_non_escape

Required event families:

- scope binding/attestation;
- boundary crossing events;
- read/write/send events for protected object classes;
- explicit release/declassification events where applicable.

## Fail-closed rules

The checker must reject or downgrade when:

- schema version is unknown;
- `inputs_hash` mismatches;
- policy bundle hash/signature is invalid;
- required coverage is absent;
- event integrity is below claim requirements;
- scope integrity is not trusted for a boundary claim;
- budgets were exceeded;
- precision loss is unreported;
- `INCONCLUSIVE` is presented as `PROVED`.

## Output

Checker output should include:

- accepted/rejected status;
- normalized verdict;
- claim id/kind;
- missing evidence if any;
- counterexample slice if violation;
- policy/admissibility hints for Policy Fabric;
- atlas metadata for Sociosphere.

## Trusted computing base

Minimum TCB:

- schema parser;
- canonicalizer;
- hash/signature verification;
- coverage rules;
- verdict checks;
- optional invariant checker or replay driver.

The certifier can be treated as untrusted if the checker validates the proof artifact or replays the analysis deterministically.
