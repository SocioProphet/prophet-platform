from __future__ import annotations

from .policy_simulation import load_policy_simulation_profile, summarize_policy_simulation_profile
from .validation import validate_json_file


class PolicySimulationMeasuredEntityError(ValueError):
    pass


def _first_release_authority(profile: dict) -> str:
    functionals = profile.get("reward_functionals", [])
    if not functionals:
        return ""
    return str(functionals[0].get("release_authority", ""))


def _first_triparty_face(profile: dict) -> dict:
    faces = profile.get("triparty_faces", [])
    if not faces:
        raise PolicySimulationMeasuredEntityError("policy simulation profile requires at least one triparty face")
    return faces[0]


def policy_simulation_measured_entity(profile: dict) -> dict:
    """Project a policy simulation profile into a UVMC advisory measured entity.

    This projection is advisory evidence only. It does not emit economic profit,
    policy correctness, live automation authority, or value-release authority.
    """
    summary = summarize_policy_simulation_profile(profile)
    face = _first_triparty_face(profile)
    donor = profile.get("donor_corpus", {})
    scenario = profile.get("scenario", {})
    audit = profile.get("audit_receipt", {})

    entity = {
        "measured_entity_id": f"policy-simulation-measured:{profile.get('profile_id', '')}",
        "profile_id": profile.get("profile_id", ""),
        "advisory_status": "advisory_evidence_only",
        "source_ref": donor.get("repository", ""),
        "measurement_context": {
            "domain": "policy_simulation",
            "scenario_ref": scenario.get("scenario_id", ""),
            "cadence": scenario.get("cadence", "synthetic"),
            "formula_version": "policy-simulation-uvmc-v0.1",
        },
        "governance_control": {
            "runtime_dependency": donor.get("runtime_dependency", False),
            "release_authority": _first_release_authority(profile),
            "live_policy_automation": False,
            "value_release_authorized": False,
        },
        "triparty_measurement": {
            "lambda_evid": float(face.get("lambda_evid", 0.0)),
            "lambda_admit": float(face.get("lambda_admit", 0.0)),
            "lambda_release": float(face.get("lambda_release", 0.0)),
            "residual": float(face.get("residual", 0.0)),
            "release_ratio": summary["release_ratio"],
            "residual_ratio": summary["residual_ratio"],
            "state": face.get("state", ""),
        },
        "calculation_receipt": {
            "run_id": audit.get("run_id", ""),
            "framework_version": audit.get("framework_version", ""),
            "input_hash": audit.get("input_hash", ""),
            "output_hash": audit.get("output_hash", ""),
            "replay_available": audit.get("replay_available", False),
        },
        "authority_refs": {
            "measurement_contract": "SocioProphet/economic-prophet:schemas/policy_simulation_profile.schema.json",
            "adoption_registry": "SocioProphet/sociosphere:registry/resource-intake-adoption.yaml#ai-economist-policy-simulation-intake",
            "learning_receipt": "SocioProphet/systems-learning-loops:kb/receipts/ai-economist-policy-simulation-intake.receipt.yaml",
            "platform_evidence_contract": "SocioProphet/prophet-platform:docs/POLICY_SIMULATION_EVIDENCE_CONTRACT.md",
        },
        "non_claims": [
            "This measured entity is advisory evidence only.",
            "This measured entity is not Economic Profit.",
            "This measured entity does not authorize live policy automation.",
            "This measured entity does not release economic value.",
            "This measured entity does not claim fairness, legality, production readiness, or policy correctness.",
        ],
    }
    validate_policy_simulation_measured_entity_semantics(entity)
    return entity


def validate_policy_simulation_measured_entity_semantics(entity: dict) -> bool:
    if entity.get("advisory_status") != "advisory_evidence_only":
        raise PolicySimulationMeasuredEntityError("advisory_status must be advisory_evidence_only")

    governance = entity.get("governance_control", {})
    if governance.get("runtime_dependency") is not False:
        raise PolicySimulationMeasuredEntityError("governance_control.runtime_dependency must be false")
    if governance.get("release_authority") != "advisory_only":
        raise PolicySimulationMeasuredEntityError("governance_control.release_authority must be advisory_only")
    if governance.get("live_policy_automation") is not False:
        raise PolicySimulationMeasuredEntityError("governance_control.live_policy_automation must be false")
    if governance.get("value_release_authorized") is not False:
        raise PolicySimulationMeasuredEntityError("governance_control.value_release_authorized must be false")
    if "economic_profit" in entity:
        raise PolicySimulationMeasuredEntityError("policy simulation measured entity must not claim economic_profit")

    triparty = entity.get("triparty_measurement", {})
    lambda_evid = float(triparty.get("lambda_evid", 0.0))
    lambda_admit = float(triparty.get("lambda_admit", 0.0))
    lambda_release = float(triparty.get("lambda_release", 0.0))
    residual = float(triparty.get("residual", 0.0))

    if lambda_admit > lambda_evid:
        raise PolicySimulationMeasuredEntityError("lambda_admit cannot exceed lambda_evid")
    if lambda_release > lambda_admit:
        raise PolicySimulationMeasuredEntityError("lambda_release cannot exceed lambda_admit")
    if abs((lambda_evid - lambda_release) - residual) > 1e-9:
        raise PolicySimulationMeasuredEntityError("residual must equal lambda_evid - lambda_release")

    non_claims = " ".join(str(item) for item in entity.get("non_claims", [])).lower()
    for fragment in ["advisory evidence", "not economic profit", "does not authorize live policy automation", "does not release economic value", "does not claim fairness"]:
        if fragment not in non_claims:
            raise PolicySimulationMeasuredEntityError(f"non_claims missing boundary fragment: {fragment}")
    return True


def run_policy_simulation_measured_entity(path: str) -> dict:
    profile = load_policy_simulation_profile(path)
    entity = policy_simulation_measured_entity(profile)
    validate_json_file_from_data(entity, "schemas/policy_simulation_measured_entity.schema.json")
    return {"measured_entity": entity, "profile": profile}


def validate_json_file_from_data(instance: dict, schema_path: str) -> bool:
    # Reuse the repo's lightweight schema validator by writing no temporary files:
    # import locally to avoid expanding public validation API in this tranche.
    import json
    from pathlib import Path

    from .validation import validate_instance

    schema = json.loads(Path(schema_path).read_text())
    return validate_instance(instance, schema)
