from app.models import AcademyRecordHeader, LearningSearchRecord
from app.repositories import LampstandJsonlAcademySearchRepository


def record(record_id: str = "lsr_0001", text: str = "Searchable explanation.") -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id=record_id, object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why recommended",
        text=text,
        target_ref="llr_0001",
        final_score=1.0,
    )


def test_lampstand_jsonl_repository_writes_jsonl(tmp_path) -> None:
    path = tmp_path / "academy-search.jsonl"
    repo = LampstandJsonlAcademySearchRepository(path)
    repo.ingest(record())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert "ALEXANDRIAN_ACADEMY" in lines[0]


def test_lampstand_jsonl_repository_upserts_by_object_id(tmp_path) -> None:
    path = tmp_path / "academy-search.jsonl"
    repo = LampstandJsonlAcademySearchRepository(path)
    repo.ingest(record("same-id", "first"))
    repo.ingest(record("same-id", "second"))
    records = repo.list_records()
    assert len(records) == 1
    assert records[0].text == "second"


def test_lampstand_jsonl_repository_clear_removes_records(tmp_path) -> None:
    path = tmp_path / "academy-search.jsonl"
    repo = LampstandJsonlAcademySearchRepository(path)
    repo.ingest(record())
    repo.clear()
    assert repo.list_records() == []
