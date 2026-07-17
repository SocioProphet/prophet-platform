"""GRLPlus → compliance-framework crosswalk.

The estate's governance moat is that GRLPlus DECIDES closure/escalation from evidence counted on the
proof-carrying graph (evaluator.py). This makes that moat auditor-legible: it maps each GRLPlus rule to
the NIST AI RMF function/subcategory and EU AI Act article it satisfies — so a GRC buyer sees "your
control X is our rule Y, and here's the graph evidence that enforced it." Static, defensible mapping;
no framework text is reproduced, only the control identifiers + a one-line rationale.
"""
from __future__ import annotations

from typing import Any

# Each GRLPlus rule → the controls it operationalizes. NIST = NIST AI RMF 1.0 function.subcategory;
# EU = EU AI Act article. Rationale ties the rule's graph-evidence check to the control's intent.
CROSSWALK: dict[str, dict[str, Any]] = {
    "CR_MIN_DIRECT_ARGUMENT_1": {
        "nist_ai_rmf": ["MAP-2.3", "MEASURE-2.9"],
        "eu_ai_act": ["Art. 11 (technical documentation)"],
        "rationale": "Requires ≥1 traceable argument on the graph before closure — documented, evidenced decisions.",
    },
    "CR_MIN_DIRECT_ARGUMENT_2": {
        "nist_ai_rmf": ["MAP-2.3", "MEASURE-2.9", "GOVERN-1.2"],
        "eu_ai_act": ["Art. 11 (technical documentation)"],
        "rationale": "Two-argument coverage raises the documentation bar for higher-stakes elements.",
    },
    "CR_MIN_EVIDENCE_LINK_1": {
        "nist_ai_rmf": ["MEASURE-2.9", "MEASURE-2.13"],
        "eu_ai_act": ["Art. 12 (record-keeping / logging)"],
        "rationale": "An evidence link must support the element — the graph IS the auditable record trail.",
    },
    "CR_MIN_TELEMETRY_ARTIFACT_1": {
        "nist_ai_rmf": ["MEASURE-2.4", "MANAGE-4.1"],
        "eu_ai_act": ["Art. 12 (record-keeping)", "Art. 15 (accuracy, robustness)"],
        "rationale": "A telemetry/control artifact must be attached — continuous monitoring evidence.",
    },
    "CR_DIVERGENCE_BELOW_WARNING": {
        "nist_ai_rmf": ["MEASURE-2.5", "MEASURE-2.7"],
        "eu_ai_act": ["Art. 15 (accuracy, robustness)"],
        "rationale": "Semantic divergence must fall below threshold before closure — validity/reliability gate.",
    },
    "CR_OWNER_APPROVAL_REQUIRED": {
        "nist_ai_rmf": ["GOVERN-2.1", "MANAGE-2.1"],
        "eu_ai_act": ["Art. 14 (human oversight)"],
        "rationale": "A named owner must approve closure — enforced human-in-the-loop accountability.",
    },
    "ER_BREACH_SLA_ONCE": {
        "nist_ai_rmf": ["MANAGE-4.1"],
        "eu_ai_act": ["Art. 9 (risk management system)"],
        "rationale": "Escalate on first SLA breach — incident response tied to the risk-management loop.",
    },
    "ER_BREACH_SLA_TWICE": {
        "nist_ai_rmf": ["MANAGE-4.1", "MANAGE-4.3"],
        "eu_ai_act": ["Art. 9 (risk management system)"],
        "rationale": "Repeated breach escalation — graduated risk treatment.",
    },
    "ER_CRITICAL_IMMEDIATE": {
        "nist_ai_rmf": ["MANAGE-2.4", "MANAGE-4.1"],
        "eu_ai_act": ["Art. 9 (risk management)", "Art. 62 (serious-incident reporting)"],
        "rationale": "Immediate escalation on critical severity — expedited incident handling.",
    },
    "ER_PERSISTENT_HIGH_TWO_REVIEWS": {
        "nist_ai_rmf": ["MANAGE-4.2"],
        "eu_ai_act": ["Art. 9 (risk management)"],
        "rationale": "Persistent high severity escalates — trend-based risk treatment.",
    },
    "ER_MISSING_DIRECT_ARGUMENT_BLOCKS_CLOSURE": {
        "nist_ai_rmf": ["GOVERN-1.2", "MAP-2.3"],
        "eu_ai_act": ["Art. 11 (technical documentation)", "Art. 14 (human oversight)"],
        "rationale": "Closure is blocked without argument coverage — a hard governance gate, not advisory.",
    },
}

FRAMEWORKS = {
    "nist_ai_rmf": "NIST AI Risk Management Framework 1.0",
    "eu_ai_act": "EU AI Act (Regulation 2024/1689)",
}


def crosswalk() -> dict[str, Any]:
    """The full GRLPlus → NIST AI RMF / EU AI Act crosswalk, with reverse indices for auditor lookup."""
    by_nist: dict[str, list[str]] = {}
    by_eu: dict[str, list[str]] = {}
    for rule, m in CROSSWALK.items():
        for c in m["nist_ai_rmf"]:
            by_nist.setdefault(c, []).append(rule)
        for c in m["eu_ai_act"]:
            by_eu.setdefault(c, []).append(rule)
    return {
        "frameworks": FRAMEWORKS,
        "rules": CROSSWALK,
        "by_nist_ai_rmf": by_nist,   # control → GRLPlus rules that satisfy it
        "by_eu_ai_act": by_eu,
        "coverage": {"rules_mapped": len(CROSSWALK), "nist_controls": len(by_nist), "eu_articles": len(by_eu)},
    }
