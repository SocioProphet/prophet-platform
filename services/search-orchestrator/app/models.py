from pydantic import BaseModel


class SearchScope(BaseModel):
    local_desktop: bool = False
    cloud_workspace: bool = True
    memory: bool = False


class SearchRequest(BaseModel):
    query_id: str
    actor_id: str
    text: str
    mode: str
    limit: int
    scope: SearchScope | None = None


class SearchResultScore(BaseModel):
    final: float


class SearchResultActions(BaseModel):
    open_local: bool = False
    open_cloud: bool = False
    summarize: bool = False
    create_task: bool = False
    draft_reply: bool = False


class SearchResult(BaseModel):
    result_id: str
    source: str
    entity_type: str
    title: str
    snippet: str | None = None
    path_or_uri: str | None = None
    score: SearchResultScore
    actions: SearchResultActions | None = None


class AcademyRecordHeader(BaseModel):
    object_id: str
    object_type: str
    object_version: str | None = None
    created_at: str | None = None
    created_by_contributor_id: str | None = None
    created_by_role: str | None = None
    status: str | None = None
    policy_tags: list[str] = []


class LearningSearchRecord(BaseModel):
    header: AcademyRecordHeader
    source: str
    entity_type: str
    title: str
    text: str
    target_ref: str
    evidence_ref_ids: list[str] = []
    memory_ref_ids: list[str] = []
    search_ref_ids: list[str] = []
    governance_ref_ids: list[str] = []
    agentplane_run_ref_ids: list[str] = []
    final_score: float = 1.0
