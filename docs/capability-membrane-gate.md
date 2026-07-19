# Gating a tool call through the capability membrane

The capability membrane (`tools/capability_membrane.py`) is the fail-closed
kernel that decides whether a single tool/connector action may run. This is the
**runtime seam**: a runtime (an agent-machine, a connector dispatcher, a
service) calls the membrane *immediately before executing* a connector action.
If the decision is not `allowed`, **the runtime must not execute the action.**

The membrane lives in `prophet-platform` and does not reach into any runtime.
Any runtime — including one in another repo — integrates by calling this seam.

## In-process (Python)

```python
from capability_membrane import gate

decision = gate({
    "surface": "shell",              # connectorKind
    "action": "shell.exec",          # the real action about to run
    "access_level": "scopedWrite",   # ConnectorActionScope.accessLevel
    "subject_ref": "urn:srcos:agent:conductor",
    "tension_members": ["policy", "identity", "provenance",
                        "evidence", "replay", "revocation"],
    "requested_autonomy_level": "L4",
    "autonomy_evidence": ["conductor_response_envelope"],
    # optional: scope, owned, object_ref, membrane_decision, risk_level,
    #           may_transmit_content, policy_refs, machine_ref
})

if not decision["allowed"]:
    raise PermissionError(decision["reasons"])
# ... only now execute the action ...
persist(decision["sealed_receipt"])   # tamper-evident evidence
```

`decision` carries `allowed`, `execution_decision` (allow|deny|ask|defer|
rewrite), `verdict`, `enforced`, `radius`, `missing_tension`, `obligations`
(e.g. `mask_fields` for a REDACT), `reasons`, and the sealed
`AgentMachineReceipt`.

## Out-of-process (any language)

Pipe a `CapabilityRequest` JSON to the CLI. **Exit 0 iff allowed** (exit 3 on a
denied/deferred decision), so a shell or non-Python runtime gates on the exit
code and reads the decision on stdout:

```bash
echo '{"surface":"shell","action":"shell.exec","access_level":"scopedWrite",
       "subject_ref":"urn:srcos:agent:conductor",
       "tension_members":["policy","identity","provenance","evidence","replay","revocation"]}' \
  | python3 tools/capability_membrane.py --request -   # exit 0 → run; non-0 → refuse
```

## What it enforces (fail-closed, all four layers)

1. **Surface class** — owned surfaces are *enforced*; foreign surfaces are
   *observed* (`verdict: observed`, advisory only — never a substitute for
   prevention).
2. **Capability radius + tension members** — the action's radius (R0–R5)
   requires a specific set of governance members present; any missing → deny.
3. **Membrane policy verdict** — ALLOW / DENY / QUARANTINE / REDACT /
   REQUIRE_SIGNATURE.
4. **Autonomy ladder** — the requested L0–L5 level must be backed by its
   evidence token.

Any single fail-closed condition dominates. See
`tools/tests/test_capability_membrane.py` for the falsifiability board that
proves each refuse/degrade/observe path fires.

## Where this plugs in next

The autonomy-*admission* gate already composes with the membrane
(`tools/emit_autonomy_admission_receipt.py`, `--surface`). The remaining
integration is the **live connector dispatcher** calling `gate()` before it
runs `shell.exec` / `computer.*` / `browser.*`. That dispatcher lives in the
agent runtime; this seam is what it calls.
