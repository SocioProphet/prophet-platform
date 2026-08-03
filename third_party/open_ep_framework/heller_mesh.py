from __future__ import annotations

import json
from pathlib import Path

from .validation import validate_json_file


CANONICAL_SPHERES = {
    "security",
    "dev",
    "forensics",
    "community",
    "attestation",
    "mesh",
    "champion",
    "packaging",
    "education",
    "federation",
    "governance",
}

SPHERE_ALIASES = {
    "developer_platform": "dev",
    "champion_challenger": "champion",
    "champion-challenger": "champion",
}


def normalize_sphere_id(sphere_id: str) -> str:
    """Normalize diagram aliases to the canonical Heller sphere names."""
    return SPHERE_ALIASES.get(sphere_id, sphere_id)


def load_heller_mesh_measurement(path: str) -> dict:
    """Load and validate a Heller mesh measurement fixture.

    This deliberately remains a measurement loader, not a token issuer or
    settlement engine. The schema enforces the minimum auditable shape for
    sphere states, transfer-pricing edges, triparty faces, and Heller supply
    summaries.
    """
    validate_json_file(path, "schemas/heller_mesh_measurement.schema.json")
    return json.loads(Path(path).read_text())


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def summarize_heller_mesh(data: dict) -> dict:
    """Compute deterministic summary metrics for a Heller mesh measurement run."""
    edges = data.get("edge_measurements", [])
    faces = data.get("triparty_faces", [])
    supply = data.get("heller_supply", {})
    sphere_ids = {sphere.get("sphere_id", "") for sphere in data.get("sphere_states", [])}
    normalized_sphere_ids = {normalize_sphere_id(sphere_id) for sphere_id in sphere_ids}

    total_credit_exposure = sum(float(edge.get("credit_exposure", 0.0)) for edge in edges)
    total_required_collateral = sum(float(edge.get("required_collateral", 0.0)) for edge in edges)
    reserve_supply = float(supply.get("reserve", 0.0))
    credit_supply = float(supply.get("credit", 0.0))

    gross_face_quantity = sum(float(face.get("lambda_evid", 0.0)) for face in faces)
    released_face_quantity = sum(float(face.get("lambda_release", 0.0)) for face in faces)
    residual_face_quantity = sum(float(face.get("residual", 0.0)) for face in faces)

    return {
        "run_id": data.get("run_id", ""),
        "scenario": data.get("scenario", ""),
        "sphere_count": len(sphere_ids),
        "known_canonical_sphere_count": len(normalized_sphere_ids & CANONICAL_SPHERES),
        "unknown_spheres": sorted(normalized_sphere_ids - CANONICAL_SPHERES),
        "edge_count": len(edges),
        "triparty_face_count": len(faces),
        "total_credit_exposure": total_credit_exposure,
        "total_required_collateral": total_required_collateral,
        "computed_reserve_adequacy": _safe_ratio(reserve_supply, total_required_collateral),
        "computed_credit_utilization": _safe_ratio(total_credit_exposure, credit_supply),
        "computed_gross_to_net_compression": _safe_ratio(released_face_quantity, gross_face_quantity),
        "residual_face_quantity": residual_face_quantity,
        "reported_reserve_adequacy": data.get("reserve_adequacy", 0.0),
        "reported_credit_utilization": data.get("credit_utilization", 0.0),
        "reported_gross_to_net_compression": data.get("gross_to_net_compression", 0.0),
    }


def run_heller_mesh(path: str) -> dict:
    """Load a Heller mesh measurement run and return summary + validated record."""
    data = load_heller_mesh_measurement(path)
    return {
        "summary": summarize_heller_mesh(data),
        "measurement": data,
    }
