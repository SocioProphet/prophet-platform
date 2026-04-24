from pathlib import Path

from app.models import AcademyRecordHeader, LearningSearchRecord
from app.repositories import LampstandCarrierAcademySearchRepository


def record() -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id="lsr_real_lampstand_0001", object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why recommended",
        text="Real Lampstand carrier smoke explanation.",
        target_ref="llr_real_lampstand_0001",
        evidence_ref_ids=["evidence://academy/span/0001"],
        final_score=1.0,
    )


def test_lampstand_carrier_repository_uses_real_lampstand_ingest(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SOCIOPROFIT_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("SOCIOPROFIT_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("SOCIOPROFIT_RUNTIME_HOME", str(tmp_path / "runtime"))

    repo = LampstandCarrierAcademySearchRepository(tmp_path / "academy-payloads")
    repo.ingest(record())

    payloads = list((tmp_path / "academy-payloads").glob("*.LearningSearchRecord.json"))
    results = list((tmp_path / "academy-payloads").glob("*.lampstand-ingest-result.json"))
    assert len(payloads) == 1
    assert len(results) == 1

    state_root = tmp_path / "state" / "prophet-platform"
    lampstand_payloads = list((state_root / "payloads" / "lampstand").glob("*.CarrierIngested.json"))
    events = list((state_root / "events" / "lampstand").glob("*.json"))
    receipts = list((state_root / "receipts" / "lampstand").glob("*.json"))
    catalog = list((state_root / "catalog" / "lampstand").glob("*.jsonl"))

    assert lampstand_payloads
    assert events
    assert receipts
    assert catalog

    ingest_result = Path(results[0]).read_text(encoding="utf-8")
    assert "carrier_ref" in ingest_result
    assert "publication_request" in ingest_result
