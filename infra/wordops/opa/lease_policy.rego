# WordOps capability-lease policy.
#
# Encodes the estate's OWN autonomy ladder (A0..A4) from
# docs/WORDOPS_APPROVAL_TO_LEASE_GOVERNANCE.md — NOT the generic
# low/medium/high/regulated of the external reference pack.
#
# Two decision points:
#   allow_issue  — may the broker MINT a lease for this request?
#   allow_action — may the gateway ADMIT a tool call under this lease?
#
# Invariant: approval is not capability. A0/A1 need no approval; A2 is policy-only;
# A3 needs explicit human approval + step-up; A4 (urgent containment / break-glass)
# needs approval OR a documented break-glass path, always with step-up-where-feasible
# and the shortest possible TTL. Every A3/A4 issuance is heavily audited downstream
# (the gateway emits an ExecutionReceipt to the ledger).
package wordops.authz

import rego.v1

default allow_issue := false

default allow_action := false

# Per-class TTL ceilings (seconds). A4 is the shortest.
ttl_ceiling := {"A0": 900, "A1": 900, "A2": 120, "A3": 60, "A4": 30}

within_ttl(rc) if input.request.ttl_seconds <= ttl_ceiling[rc]

# ---------------------------------------------------------------------------
# allow_issue — lease minting
# ---------------------------------------------------------------------------

# A0 Observe-only: read:* scopes, no approval.
allow_issue if {
	input.request.risk_class == "A0"
	within_ttl("A0")
	every s in input.request.scope {
		startswith(s, "read:")
	}
}

# A1 Draft-only: non-mutating draft:/propose: scopes, no approval.
allow_issue if {
	input.request.risk_class == "A1"
	within_ttl("A1")
	every s in input.request.scope {
		non_mutating(s)
	}
}

# A2 Low-risk execute: policy-only. Requires an operator role; step-up recommended not required.
# Containment sever is intrinsically A4 and can never be minted here.
allow_issue if {
	input.request.risk_class == "A2"
	within_ttl("A2")
	has_role({"ops-operator", "ops-admin"})
	not containment_request
}

# A3 High-risk execute: explicit human approval + satisfied step-up.
allow_issue if {
	input.request.risk_class == "A3"
	within_ttl("A3")
	has_role({"change-approver", "ops-admin"})
	input.request.approval_id != ""
	input.request.step_up_satisfied == true
	not containment_request
}

# A4 Emergency constrained action (e.g. urgent containment / break-glass).
# Either an explicit approval, OR a documented break-glass path — both with step-up.
allow_issue if {
	input.request.risk_class == "A4"
	within_ttl("A4")
	responder_role
	a4_authorized
	input.request.step_up_satisfied == true
}

responder_role if has_role({"responder", "incident-commander", "ops-admin"})

a4_authorized if input.request.approval_id != ""

a4_authorized if {
	input.request.break_glass == true
	input.request.break_glass_policy_ref != ""
}

# A containment sever is intrinsically A4; the lower-class rules exclude it via
# `not containment_request`, so it can only ever be minted through the A4 path.
containment_request if {
	some s in input.request.scope
	startswith(s, "containment:sever")
}

# ---------------------------------------------------------------------------
# allow_action — gateway admission of a tool call under a live lease
# ---------------------------------------------------------------------------

allow_action if {
	input.action == "invoke"
	input.lease.active == true
	audience_matches
	scope_covers(input.resource.required_scope)
}

audience_matches if input.lease.aud == input.resource.audience

scope_covers(req) if input.lease.scope[_] == req

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

non_mutating(s) if startswith(s, "draft:")

non_mutating(s) if startswith(s, "propose:")

has_role(allowed) if {
	some r in input.user.roles
	allowed[r]
}
