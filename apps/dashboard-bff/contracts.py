from pydantic import BaseModel


class OverviewResponse(BaseModel):
    service: str
    views: list[str]
    trace_required: bool = True
    evidence_required: bool = True
