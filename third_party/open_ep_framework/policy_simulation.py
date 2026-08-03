from __future__ import annotations

import json
from pathlib import Path

from .validation import validate_json_file


class PolicySimulationProfileError(ValueError):
    pass


def _require_nonnegative(value: float, path: str) -> None:
    if value < 0.0:
        raise PolicySimulationProfileError(f"{path} must be nonnegative")


def validate_policy_simulation_profile_semantics(data: dict) -> bool:
    """Apply Economic Prophet semantic gates for policy simulation profiles.

    JSON schema validation proves the shape. These gates prove the v0.1
    source-intake posture: donor runtimes stay out, reward scores remain
    advisory, and triparty quantities preserve gross/admit/release/residual
    ordering.
    """
    donor = data.get("donor_corpus", {})
    if donor.get("runtime_dependency") is not False:
        raise PolicySimulationProfileError("donor_corpus.runtime_dependency must be false")

    for idx, functional in enumerate(data.get("reward_functionals", [])):
        if functional.get("release_authority") != "advisory_only":
            raise PolicySimulationProfileError(
                f"reward_functionals[{idx}].release_authority must be advisory_only"
            )

    for idx, face in enumerate(data.get("triparty_faces", [])):
        lambda_evid = float(face.get("lambda_evid", 0.0))
        lambda_admit = float(face.get("lambda_admit", 0.0))
        lambda_release = float(face.get("lambda_release", 0.0))
        residual = float(face.get("residual", 0.0))

        _require_nonnegative(lambda_evid, f"triparty_faces[{idx}].lambda_evid")
        _require_nonnegative(lambda_admit, f"triparty_faces[{idx}].lambda_admit")
        _require_nonnegative(lambda_release, f"triparty_faces[{idx}].lambda_release")
        _require_nonnegative(residual, f"triparty_faces[{idx}].residual")

        if lambda_admit > lambda_evid:
            raise PolicySimulationProfileError(
                f"triparty_faces[{idx}].lambda_admit cannot exceed lambda_evid"
            )
        if lambda_release > lambda_admit:
            raise PolicySimulationProfileError(
                f"triparty_faces[{idx}].lambda_release cannot exceed lambda_admit"
            )
        if abs((lambda_evid - lambda_release) - residual) > 1e-9:
            raise PolicySimulationProfileError(
                f"triparty_faces[{idx}].residual must equal lambda_evid - lambda_release"
            )

    return True


def load_policy_simulation_profile(path: str) -> dict:
    """Load and validate a policy simulation profile.

    The profile is a schema-first assimilation boundary for economic simulation
    patterns. It deliberately does not import donor runtimes, start training jobs,
    or authorize live policy actions.
    """
    validate_json_file(path, "schemas/policy_simulation_profile.schema.json")
    data = json.loads(Path(path).read_text())
    validate_policy_simulation_profile_semantics(data)
    return data


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def summarize_policy_simulation_profile(data: dict) -> dict:
    """Return deterministic audit-facing summary metrics for a profile."""
    faces = data.get("triparty_faces", [])
    gross_quantity = sum(float(face.get("lambda_evid", 0.0)) for face in faces)
    admitted_quantity = sum(float(face.get("lambda_admit", 0.0)) for face in faces)
    released_quantity = sum(float(face.get("lambda_release", 0.0)) for face in faces)
    residual_quantity = sum(float(face.get("residual", 0.0)) for face in faces)

    return {
        "profile_id": data.get("profile_id", ""),
        "scenario_id": data.get("scenario", {}).get("scenario_id", ""),
        "actor_count": len(data.get("actors", [])),
        "component_count": len(data.get("components", [])),
        "reward_functional_count": len(data.get("reward_functionals", [])),
        "triparty_face_count": len(faces),
        "runtime_dependency": data.get("donor_corpus", {}).get("runtime_dependency", False),
        "gross_quantity": gross_quantity,
        "admitted_quantity": admitted_quantity,
        "released_quantity": released_quantity,
        "residual_quantity": residual_quantity,
        "admission_ratio": _safe_ratio(admitted_quantity, gross_quantity),
        "release_ratio": _safe_ratio(released_quantity, gross_quantity),
        "residual_ratio": _safe_ratio(residual_quantity, gross_quantity),
        "replay_available": data.get("audit_receipt", {}).get("replay_available", False),
    }


def run_policy_simulation_profile(path: str) -> dict:
    """Load a profile and return summary plus validated profile data."""
    data = load_policy_simulation_profile(path)
    return {
        "summary": summarize_policy_simulation_profile(data),
        "profile": data,
    }
