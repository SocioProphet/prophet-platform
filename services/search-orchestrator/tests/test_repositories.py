from app.models import AcademyRecordHeader, LearningSearchRecord
from app.repositories import InMemoryAcademySearchRepository


def record(record_id: str = "lsr_00000001") -> LearningSearchRecord:
    return LearningSearchRecord(
        header=AcademyRecordHeader(
            object_id=record_id,
            object_type="LearningSearchRecord",
            policy_tags=["learning-loop", "search"],
        ),
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


def test_in_memory_academy_repository_ingests_and_lists_records() -> None:
    repo = InMemoryAcademySearchRepository()
    repo.ingest(record())
    records = repo.list_records()
    assert len(records) == 1
    assert records[0].header.object_id == "lsr_00000001"


def test_in_memory_academy_repository_clear_removes_records() -> None:
    repo = InMemoryAcademySearchRepository()
    repo.ingest(record())
    repo.clear()
    assert repo.list_records() == []
