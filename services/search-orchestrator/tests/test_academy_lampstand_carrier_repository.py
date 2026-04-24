from app.models import AcademyRecordHeader, LearningSearchRecord
from app.repositories import LampstandCarrierAcademySearchRepository


def record(record_id: str = "lsr_carrier_0001") -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id=record_id, object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why recommended",
        text="Carrier ingest explanation.",
        target_ref="llr_carrier_0001",
        final_score=1.0,
    )


def test_lampstand_carrier_repository_materializes_payload_and_result(tmp_path, monkeypatch) -> None:
    calls = []

    def fake_ingest(self, path):
        calls.append(str(path))
        return {
            "ok": True,
            "carrier_ref": "carrier://test",
            "payload_path": str(path),
            "receipt_path": str(tmp_path / "receipt.json"),
            "catalog_path": str(tmp_path / "catalog.json"),
        }

    monkeypatch.setattr(LampstandCarrierAcademySearchRepository, "_ingest_path", fake_ingest)
    repo = LampstandCarrierAcademySearchRepository(tmp_path)
    repo.ingest(record())

    payloads = list(tmp_path.glob("*.LearningSearchRecord.json"))
    results = list(tmp_path.glob("*.lampstand-ingest-result.json"))
    assert len(payloads) == 1
    assert len(results) == 1
    assert calls == [str(payloads[0])]
    assert repo.list_records()[0].source == "ALEXANDRIAN_ACADEMY"


def test_lampstand_carrier_repository_clear_removes_payload_and_result(tmp_path, monkeypatch) -> None:
    def fake_ingest(self, path):
        return {"ok": True, "payload_path": str(path)}

    monkeypatch.setattr(LampstandCarrierAcademySearchRepository, "_ingest_path", fake_ingest)
    repo = LampstandCarrierAcademySearchRepository(tmp_path)
    repo.ingest(record())
    repo.clear()

    assert list(tmp_path.glob("*.LearningSearchRecord.json")) == []
    assert list(tmp_path.glob("*.lampstand-ingest-result.json")) == []
