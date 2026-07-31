package wordops.authz

import rego.v1

# ---- allow_issue: happy paths per class ----

test_a0_read_only_allowed if {
	allow_issue with input as {
		"user": {"id": "svc", "roles": []},
		"request": {"risk_class": "A0", "ttl_seconds": 300, "scope": ["read:rooms", "read:tickets"]},
	}
}

test_a1_draft_allowed if {
	allow_issue with input as {
		"user": {"id": "svc", "roles": []},
		"request": {"risk_class": "A1", "ttl_seconds": 600, "scope": ["draft:case-update"]},
	}
}

test_a2_low_risk_execute_requires_operator if {
	allow_issue with input as {
		"user": {"id": "op", "roles": ["ops-operator"]},
		"request": {"risk_class": "A2", "ttl_seconds": 60, "scope": ["ticket:create"]},
	}
}

test_a3_high_risk_requires_approval_and_stepup if {
	allow_issue with input as {
		"user": {"id": "boss", "roles": ["change-approver"]},
		"request": {"risk_class": "A3", "ttl_seconds": 60, "scope": ["platform:mutate"], "approval_id": "APR-9", "step_up_satisfied": true},
	}
}

test_a4_containment_with_approval_allowed if {
	allow_issue with input as {
		"user": {"id": "resp", "roles": ["responder"]},
		"request": {"risk_class": "A4", "ttl_seconds": 30, "scope": ["containment:sever:full"], "approval_id": "APR-INC-1", "step_up_satisfied": true},
	}
}

test_a4_containment_break_glass_allowed if {
	allow_issue with input as {
		"user": {"id": "ic", "roles": ["incident-commander"]},
		"request": {"risk_class": "A4", "ttl_seconds": 15, "scope": ["containment:sever:selective"], "approval_id": "", "break_glass": true, "break_glass_policy_ref": "policy://break-glass/v1", "step_up_satisfied": true},
	}
}

# ---- allow_issue: denials (teeth) ----

test_containment_below_a4_denied if {
	not allow_issue with input as {
		"user": {"id": "resp", "roles": ["responder", "ops-admin"]},
		"request": {"risk_class": "A2", "ttl_seconds": 30, "scope": ["containment:sever:full"], "approval_id": "APR-1", "step_up_satisfied": true},
	}
}

test_a4_without_approval_or_breakglass_denied if {
	not allow_issue with input as {
		"user": {"id": "resp", "roles": ["responder"]},
		"request": {"risk_class": "A4", "ttl_seconds": 30, "scope": ["containment:sever:full"], "approval_id": "", "break_glass": false, "step_up_satisfied": true},
	}
}

test_a3_without_approval_denied if {
	not allow_issue with input as {
		"user": {"id": "boss", "roles": ["change-approver"]},
		"request": {"risk_class": "A3", "ttl_seconds": 60, "scope": ["platform:mutate"], "approval_id": "", "step_up_satisfied": true},
	}
}

test_ttl_over_ceiling_denied if {
	not allow_issue with input as {
		"user": {"id": "resp", "roles": ["responder"]},
		"request": {"risk_class": "A4", "ttl_seconds": 31, "scope": ["containment:sever:full"], "approval_id": "APR-1", "step_up_satisfied": true},
	}
}

test_a0_non_read_scope_denied if {
	not allow_issue with input as {
		"user": {"id": "svc", "roles": []},
		"request": {"risk_class": "A0", "ttl_seconds": 60, "scope": ["read:rooms", "ticket:create"]},
	}
}

# ---- allow_action ----

test_action_admitted_when_scope_and_audience_match if {
	allow_action with input as {
		"action": "invoke",
		"lease": {"active": true, "aud": "mcp://gbrg-containment", "scope": ["containment:sever:full"]},
		"resource": {"kind": "mcp_tool", "name": "sever_endpoint", "audience": "mcp://gbrg-containment", "required_scope": "containment:sever:full"},
	}
}

test_action_denied_on_audience_mismatch if {
	not allow_action with input as {
		"action": "invoke",
		"lease": {"active": true, "aud": "mcp://openproject", "scope": ["containment:sever:full"]},
		"resource": {"kind": "mcp_tool", "name": "sever_endpoint", "audience": "mcp://gbrg-containment", "required_scope": "containment:sever:full"},
	}
}

test_action_denied_when_lease_inactive if {
	not allow_action with input as {
		"action": "invoke",
		"lease": {"active": false, "aud": "mcp://gbrg-containment", "scope": ["containment:sever:full"]},
		"resource": {"kind": "mcp_tool", "name": "sever_endpoint", "audience": "mcp://gbrg-containment", "required_scope": "containment:sever:full"},
	}
}
