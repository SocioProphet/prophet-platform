from __future__ import annotations

import app.intelligence_repositories as intelligence_repositories


def test_get_frontier_provenance_is_parameterized(monkeypatch):
    seen = {}

    def fake(sql, parameters=None):
        seen["sql"] = sql
        seen["parameters"] = parameters
        return []

    monkeypatch.setattr(intelligence_repositories, "ch_query", fake)
    intelligence_repositories.get_frontier_provenance(limit=7)

    assert "{limit:UInt64}" in seen["sql"]
    assert seen["parameters"] == {"limit": 7}


def test_get_reproduced_vs_claimed_uses_positional_params_and_derives_state(monkeypatch):
    seen = {}

    def fake(sql, params=()):
        seen["sql"] = sql
        seen["params"] = params
        return [
            {
                "provider_id": "openai",
                "reproduced_by_us": False,
                "source_trust_class": "official_provider",
                "freshness_days": 5,
                "strategic_relevance": "high",
                "crosswalk_count": 3,
            },
            {
                "provider_id": "our_platform",
                "reproduced_by_us": True,
                "source_trust_class": "internal_reproduced",
                "freshness_days": 0,
                "strategic_relevance": "high",
                "crosswalk_count": 5,
            },
        ]

    monkeypatch.setattr(intelligence_repositories, "pg_fetch", fake)
    rows = intelligence_repositories.get_reproduced_vs_claimed(limit=11)

    assert "limit %s" in seen["sql"]
    assert seen["params"] == (11,)
    assert rows[0]["coverage_state"] == "claimed_only"
    assert rows[1]["coverage_state"] == "reproduced"
