from typing import Literal

from pydantic import BaseModel, Field


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
    workspace_id: str | None = None
    jurisdiction_id: str | None = None
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
    policy_tags: list[str] = Field(default_factory=list)


class AcademyVisibility(BaseModel):
    allowed_actor_ids: list[str] = Field(default_factory=list)
    allowed_workspace_ids: list[str] = Field(default_factory=list)
    allowed_jurisdiction_ids: list[str] = Field(default_factory=list)


class LearningSearchRecord(BaseModel):
    header: AcademyRecordHeader
    source: Literal["ALEXANDRIAN_ACADEMY"]
    entity_type: Literal["LEARNING_ACTION_EXPLANATION", "LEARNING_LOOP_RECORD"]
    title: str
    text: str
    target_ref: str
    evidence_ref_ids: list[str] = Field(default_factory=list)
    memory_ref_ids: list[str] = Field(default_factory=list)
    search_ref_ids: list[str] = Field(default_factory=list)
    governance_ref_ids: list[str] = Field(default_factory=list)
    agentplane_run_ref_ids: list[str] = Field(default_factory=list)
    visibility: AcademyVisibility | None = None
    final_score: float = Field(default=1.0, ge=0, le=1)
