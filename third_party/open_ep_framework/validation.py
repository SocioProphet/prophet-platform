import json
from pathlib import Path


class ValidationError(ValueError):
    pass


def _check_type(value, expected, path):
    if expected == "object" and not isinstance(value, dict):
        raise ValidationError(f"{path} must be object")
    if expected == "array" and not isinstance(value, list):
        raise ValidationError(f"{path} must be array")
    if expected == "string" and not isinstance(value, str):
        raise ValidationError(f"{path} must be string")
    if expected == "boolean" and not isinstance(value, bool):
        raise ValidationError(f"{path} must be boolean")
    if expected == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        raise ValidationError(f"{path} must be number")
    if expected == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValidationError(f"{path} must be integer")


def validate_instance(instance, schema, path="$"):
    schema_type = schema.get("type")
    if schema_type:
        _check_type(instance, schema_type, path)

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                raise ValidationError(f"{path}.{key} is required")
        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in instance:
                validate_instance(instance[key], sub_schema, f"{path}.{key}")

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if item_schema:
            for idx, item in enumerate(instance):
                validate_instance(item, item_schema, f"{path}[{idx}]")
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValidationError(f"{path} below minItems")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ValidationError(f"{path} above maxItems")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{path} below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{path} above maximum")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            raise ValidationError(f"{path} below exclusive minimum")
    return True


def validate_json_file(instance_path: str, schema_path: str) -> bool:
    instance = json.loads(Path(instance_path).read_text())
    schema = json.loads(Path(schema_path).read_text())
    return validate_instance(instance, schema)
