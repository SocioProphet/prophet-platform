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


class SearchResult(BaseModel):
    result_id: str
    source: str
    entity_type: str
    title: str
    score: SearchResultScore
