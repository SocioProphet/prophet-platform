from __future__ import annotations

import sys
from pathlib import Path


def _load_semantic_bridge_validators():
    try:
        from semantic_bridge.validators import (  # type: ignore
            validate_zone_publication_plan,
            validate_zone_publication_record,
            validate_zone_publication_request,
        )
        return (
            validate_zone_publication_request,
            validate_zone_publication_plan,
            validate_zone_publication_record,
        )
    except Exception:
        repo_root = Path(__file__).resolve().parents[4]
        semantic_src = repo_root / "apps" / "semantic-bridge" / "src"
        if str(semantic_src) not in sys.path:
            sys.path.insert(0, str(semantic_src))
        from semantic_bridge.validators import (  # type: ignore
            validate_zone_publication_plan,
            validate_zone_publication_record,
            validate_zone_publication_request,
        )
        return (
            validate_zone_publication_request,
            validate_zone_publication_plan,
            validate_zone_publication_record,
        )


def validate_request(payload):
    validate_zone_publication_request, _, _ = _load_semantic_bridge_validators()
    return validate_zone_publication_request(payload)


def validate_plan(payload):
    _, validate_zone_publication_plan, _ = _load_semantic_bridge_validators()
    return validate_zone_publication_plan(payload)


def validate_record(payload):
    _, _, validate_zone_publication_record = _load_semantic_bridge_validators()
    return validate_zone_publication_record(payload)
