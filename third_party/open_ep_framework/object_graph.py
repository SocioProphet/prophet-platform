from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .validation import validate_instance


@dataclass(frozen=True)
class CanonicalObject:
    object_id: str
    object_type: str
    as_of: str
    source_system: str
    cadence: str
    parent_id: str = ""
    legal_entity_id: str = ""
    line_of_business_id: str = ""
    relationship_id: str = ""
    account_id: str = ""
    instrument_id: str = ""
    transaction_event_id: str = ""


class ObjectGraphError(ValueError):
    pass


def load_canonical_object_schema(schema_path: str = "schemas/canonical_object.schema.json") -> dict:
    return json.loads(Path(schema_path).read_text())


class ObjectGraph:
    def __init__(self, objects: Iterable[CanonicalObject]):
        self.objects = {obj.object_id: obj for obj in objects}
        if len(self.objects) == 0:
            raise ObjectGraphError("object graph must contain at least one object")

    @classmethod
    def from_dicts(cls, records: list[dict], validate: bool = False, schema_path: str = "schemas/canonical_object.schema.json") -> "ObjectGraph":
        if validate:
            schema = load_canonical_object_schema(schema_path)
            for record in records:
                validate_instance(record, schema)
        return cls(CanonicalObject(**record) for record in records)

    @classmethod
    def from_json_file(cls, path: str, validate: bool = True, schema_path: str = "schemas/canonical_object.schema.json") -> "ObjectGraph":
        records = json.loads(Path(path).read_text())
        if not isinstance(records, list):
            raise ObjectGraphError("object graph JSON must be a list of canonical objects")
        return cls.from_dicts(records, validate=validate, schema_path=schema_path)

    def get(self, object_id: str) -> CanonicalObject:
        try:
            return self.objects[object_id]
        except KeyError as exc:
            raise ObjectGraphError(f"unknown object_id: {object_id}") from exc

    def ancestors(self, object_id: str) -> list[CanonicalObject]:
        path: list[CanonicalObject] = []
        seen: set[str] = set()
        current = self.get(object_id)
        while current.parent_id:
            if current.parent_id in seen:
                raise ObjectGraphError(f"cycle detected at {current.parent_id}")
            seen.add(current.parent_id)
            parent = self.get(current.parent_id)
            path.append(parent)
            current = parent
        return path

    def lineage(self, object_id: str) -> dict:
        obj = self.get(object_id)
        ancestors = self.ancestors(object_id)
        return {
            "object_id": obj.object_id,
            "object_type": obj.object_type,
            "as_of": obj.as_of,
            "source_system": obj.source_system,
            "cadence": obj.cadence,
            "parent_chain": [parent.object_id for parent in ancestors],
            "type_chain": [obj.object_type] + [parent.object_type for parent in ancestors],
            "legal_entity_id": obj.legal_entity_id,
            "line_of_business_id": obj.line_of_business_id,
            "relationship_id": obj.relationship_id,
            "account_id": obj.account_id,
            "instrument_id": obj.instrument_id,
            "transaction_event_id": obj.transaction_event_id,
        }


def lineage_aware_output(object_id: str, graph: ObjectGraph, components: dict) -> dict:
    return {
        "lineage": graph.lineage(object_id),
        "components": components,
    }
