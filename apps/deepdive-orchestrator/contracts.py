from pydantic import BaseModel
from typing import Optional


class DeepDiveRunRequest(BaseModel):
    mode: str
    subject_ref: str
    prompt: str = ""
    case_ref: Optional[str] = None


class DeepDiveFinding(BaseModel):
    title: str
    severity: str
    evidence_refs: list[str]


class DeepDiveRunResponse(BaseModel):
    service: str
    mode: str
    subject_ref: str
    status: str = "succeeded"
    findings: list[DeepDiveFinding]
    trace_required: bool = True
    evidence_required: bool = True
