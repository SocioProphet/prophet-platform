from pathlib import Path
import json

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from services.wopi_host.app.main import app


ROOT = Path(__file__).resolve().parents[3]
client = TestClient(app)


def _load_schema(path: str) -> dict[str, object]:
    with (ROOT / path).open("r", encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return schema


def _assert_valid(schema_path: str, payload: dict[str, object]) -> None:
    schema = _load_schema(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: list(error.path))
    assert errors == []


def test_wopi_put_file_records_validate_against_office_runtime_schemas() -> None:
    document_id = "schema-contract-doc"

    response = client.post(
        f"/v0/wopi/put-file/{document_id}",
        json={"payload": "contract aligned payload"},
    )
    assert response.status_code == 200
    payload = response.json()

    _assert_valid("schemas/office/office_document_record.schema.json", payload["document_record"])
    _assert_valid("schemas/office/office_session_record.schema.json", payload["session_record"])
    _assert_valid("schemas/office/office_version_record.schema.json", payload["version_record"])
    _assert_valid("schemas/office/office_writeback_record.schema.json", payload["writeback_record"])

    assert payload["document_record"]["source_provider"] == "SOURCEOS"
    assert payload["version_record"]["execution_backend"] == "COLLABORA"
    assert payload["writeback_record"]["status"] == "COMMITTED"
    assert payload["writeback_record"]["result_version_id"] == payload["version_record"]["version_id"]


def test_wopi_lock_session_record_validates_against_session_schema() -> None:
    document_id = "schema-lock-doc"

    response = client.post(f"/v0/wopi/lock/{document_id}")
    assert response.status_code == 200
    payload = response.json()

    _assert_valid("schemas/office/office_session_record.schema.json", payload["session_record"])
    assert payload["session_record"]["status"] == "OPEN"

    unlock = client.post(f"/v0/wopi/unlock/{document_id}")
    assert unlock.status_code == 200
    unlock_payload = unlock.json()
    _assert_valid("schemas/office/office_session_record.schema.json", unlock_payload["session_record"])
    assert unlock_payload["session_record"]["status"] == "CLOSED"
