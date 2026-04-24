from app.models import AcademyRecordHeader, LearningSearchRecord
from app.repositories import JsonFileAcademySearchRepository


def record(record_id: str = "lsr_00000001") -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(object_id=record_id, object_type="LearningSearchRecord"),
        source="ALEXANDRIAN_ACADEMY",
        entity_type="LEARNING_ACTION_EXPLANATION",
        title="Why next learning action was recommended",
        text="Review cited evidence before attempting the next item.",
        target_ref="llr_00000001",
        evidence_ref_ids=["ariadne.span.example.0001"],
        memory_ref_ids=["memory-mesh://learning-context/example-0001"],
        search_ref_ids=["sherlock://learning-search/example-0001"],
        governance_ref_ids=["policy-fabric://decision/example-0001"],
        agentplane_run_ref_ids=["agentplane://run/example-0001"],
        final_score=1.0,
    )


def test_json_file_repository_persists_records_across_instances(tmp_path) -> None:
    path = tmp_path / "academy-search.json"
    first = JsonFileAcademySearchRepository(path)
    first.ingest(record())

    second = JsonFileAcademySearchRepository(path)
    records = second.list_records()

    assert len(records) == 1
    assert records[0].header.object_id == "lsr_00000001"
    assert records[0].source == "ALEXANDRIAN_ACADEMY"


def test_json_file_repository_clear_removes_file_records(tmp_path) -> None:
    path = tmp_path / "academy-search.json"
    repo = JsonFileAcademySearchRepository(path)
    repo.ingest(record())
    repo.clear()

    assert repo.list_records() == []
