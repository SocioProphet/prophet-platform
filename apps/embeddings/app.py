"""First-party sovereign embeddings service.

Serves nomic-embed-text over an OpenAI-compatible POST /v1/embeddings, so memoryd (and anything else
that speaks the /v1/embeddings shape) gets real semantic vectors instead of the lexical/hashing fallback.
Built by prophet-platform CI and pulled from the sovereign registry — no docker.io, no external model
pull at runtime (the model is baked into the image at build time).
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

MODEL_ID = os.getenv("EMBEDDINGS_MODEL_ID", "nomic-ai/nomic-embed-text-v1.5")

# Loaded once at startup. The model is already on disk (baked in the image), so this is fast and offline.
_model = SentenceTransformer(MODEL_ID, trust_remote_code=True)
DIMENSION = _model.get_sentence_embedding_dimension()

app = FastAPI(title="sovereign-embeddings")


class EmbeddingsRequest(BaseModel):
    input: str | list[str]
    # Accepted for OpenAI/Ollama compatibility; ignored — this service serves exactly one model.
    model: str | None = None


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "model": MODEL_ID, "dimension": DIMENSION}


@app.post("/v1/embeddings")
def embeddings(req: EmbeddingsRequest) -> dict:
    texts = [req.input] if isinstance(req.input, str) else list(req.input)
    # normalize so cosine == dot; store and query share one vector space.
    vectors = _model.encode(texts, normalize_embeddings=True)
    data = [
        {"object": "embedding", "index": i, "embedding": vec.tolist()}
        for i, vec in enumerate(vectors)
    ]
    return {"object": "list", "data": data, "model": MODEL_ID}
