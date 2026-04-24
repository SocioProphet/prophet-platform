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
