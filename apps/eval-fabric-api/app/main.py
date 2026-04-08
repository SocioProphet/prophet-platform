from fastapi import FastAPI

app = FastAPI(title="Prophet Platform Eval Fabric", version="0.1.0")

_FRONTIER = {
    "profile_id": "profile.high_assurance_enterprise_agent",
    "subjects": [
        {
            "subject_id": "model.semantic-stack.2026-04-05",
            "score": 0.782,
            "rank": 2,
            "quality": 0.81,
            "safety": 0.96,
            "latency_p95_ms": 4870,
            "cost_per_safe_task": 1.84,
        },
        {
            "subject_id": "gpt5_aug2025",
            "score": 0.801,
            "rank": 1,
            "quality": 0.86,
            "safety": 0.94,
            "latency_p95_ms": 5200,
            "cost_per_safe_task": 2.11,
        },
    ],
}

_DOSSIER = {
    "model_release_id": "model.semantic-stack.2026-04-05",
    "summary": {
        "denotation_accuracy": 0.84,
        "false_allow_rate": 0.0005,
        "latency_ms_p95": 4870,
    },
    "notes": [
        "Seeded dossier payload for platform UI wiring.",
        "Next step is persisted reads from Postgres and ClickHouse.",
    ],
}

_RADAR = {
    "lane": "high_assurance_enterprise_agent",
    "competitors": [
        {
            "provider": "openai",
            "model_release_id": "gpt5_aug2025",
            "strategic_relevance": "high",
            "source_trust_class": "official_provider",
        },
        {
            "provider": "google",
            "model_release_id": "gemini_family_current",
            "strategic_relevance": "high",
            "source_trust_class": "official_provider",
        },
    ],
}

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "service": "eval-fabric-api"}

@app.get("/v1/frontier")
def frontier() -> dict:
    return _FRONTIER

@app.get("/v1/models/{model_release_id}/dossier")
def dossier(model_release_id: str) -> dict:
    payload = dict(_DOSSIER)
    payload["model_release_id"] = model_release_id
    return payload

@app.get("/v1/competition/radar")
def radar() -> dict:
    return _RADAR
