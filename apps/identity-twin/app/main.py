"""identity-twin HTTP surface — the federation-facing Multiverseal Twin.

Endpoints wire the vendored twin library (via app.core.TwinService) and never leak a raw
hypervector: attest returns a verifiable reference + medium fingerprint; verify is fail-closed;
recall returns fidelity; medium/diff return tamper-evident fingerprints and the interferometric
fringe; interfere demonstrates the "reads fringes, not scores" thesis."""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core import Reference, TwinService, UnknownSnapshot

app = FastAPI(
    title="identity-twin",
    version="0.1.0",
    description="Federation-facing Multiverseal Twin — reference-at-ingest, reads fringes not scores.",
)

_service = TwinService()


def get_service() -> TwinService:
    return _service


# ---- request/response models ----
class AttestRequest(BaseModel):
    context: str = Field(min_length=1)
    value: str = Field(min_length=1)


class AttestResponse(BaseModel):
    context: str
    proof: str
    verify_key: str
    medium_digest: str
    records: int
    d: int


class VerifyRequest(BaseModel):
    context: str
    proof: str
    verify_key: str


class VerifyResponse(BaseModel):
    verified: bool


class RecallRequest(BaseModel):
    context: str = Field(min_length=1)
    value: str = Field(min_length=1)


class RecallResponse(BaseModel):
    context: str
    fidelity: float
    matches: bool


class MediumResponse(BaseModel):
    digest: str
    records: int
    d: int


class DiffRequest(BaseModel):
    from_digest: str = Field(min_length=1)


class DiffResponse(BaseModel):
    from_digest: str
    to_digest: str
    changed: bool
    phase_energy: float
    max_fringe: float
    moved_components: int
    total_components: int


class InterfereRequest(BaseModel):
    value: str = Field(min_length=1)
    context_a: str = Field(min_length=1)
    context_b: str = Field(min_length=1)


class InterfereResponse(BaseModel):
    magnitude_similarity: float
    phase_energy: float
    provenance_moved: bool
    score_blind: bool
    fringe_visible: bool


# ---- endpoints ----
@app.get("/health")
def health(svc: TwinService = Depends(get_service)) -> dict:
    _, records = svc.medium()
    return {"status": "ok", "records": records, "d": svc.d}


@app.post("/attest", response_model=AttestResponse)
def attest(req: AttestRequest, svc: TwinService = Depends(get_service)) -> AttestResponse:
    ref, digest, count = svc.attest(req.context, req.value)
    return AttestResponse(
        context=ref.context, proof=ref.proof, verify_key=ref.verify_key,
        medium_digest=digest, records=count, d=svc.d,
    )


@app.post("/verify", response_model=VerifyResponse)
def verify(req: VerifyRequest, svc: TwinService = Depends(get_service)) -> VerifyResponse:
    return VerifyResponse(verified=svc.verify(Reference(req.context, req.proof, req.verify_key)))


@app.post("/recall", response_model=RecallResponse)
def recall(req: RecallRequest, svc: TwinService = Depends(get_service)) -> RecallResponse:
    try:
        fidelity, matches = svc.recall(req.context, req.value)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"nothing attested under context {req.context!r}")
    return RecallResponse(context=req.context, fidelity=fidelity, matches=matches)


@app.get("/medium", response_model=MediumResponse)
def medium(svc: TwinService = Depends(get_service)) -> MediumResponse:
    digest, records = svc.medium()
    return MediumResponse(digest=digest, records=records, d=svc.d)


@app.post("/diff", response_model=DiffResponse)
def diff(req: DiffRequest, svc: TwinService = Depends(get_service)) -> DiffResponse:
    try:
        return DiffResponse(**svc.diff(req.from_digest))
    except UnknownSnapshot:
        raise HTTPException(status_code=404, detail="unknown medium snapshot digest")


@app.post("/interfere", response_model=InterfereResponse)
def interfere(req: InterfereRequest, svc: TwinService = Depends(get_service)) -> InterfereResponse:
    return InterfereResponse(**svc.interfere(req.value, req.context_a, req.context_b))
