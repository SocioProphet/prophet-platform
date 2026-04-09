from __future__ import annotations

import app.repositories as repositories


def test_get_frontier_is_parameterized(monkeypatch):
    seen = {}
    probe = "profile' OR 1=1 --"

    def fake(sql, parameters=None):
        seen["sql"] = sql
        seen["parameters"] = parameters
        return []

    monkeypatch.setattr(repositories, "ch_query", fake)
    repositories.get_frontier(profile_id=probe, limit=7)

    assert "{profile_id:String}" in seen["sql"]
    assert "{limit:UInt64}" in seen["sql"]
    assert probe not in seen["sql"]
    assert seen["parameters"] == {"profile_id": probe, "limit": 7}


def test_get_model_dossier_is_parameterized(monkeypatch):
    seen = {}
    probe = "model' OR 1=1 --"

    def fake(sql, parameters=None):
        seen["sql"] = sql
        seen["parameters"] = parameters
        return []

    monkeypatch.setattr(repositories, "ch_query", fake)
    repositories.get_model_dossier(probe, limit=9)

    assert "{model_release_id:String}" in seen["sql"]
    assert "{limit:UInt64}" in seen["sql"]
    assert probe not in seen["sql"]
    assert seen["parameters"] == {"model_release_id": probe, "limit": 9}


def test_get_competition_radar_uses_positional_params(monkeypatch):
    seen = {}

    def fake(sql, params=()):
        seen["sql"] = sql
        seen["params"] = params
        return []

    monkeypatch.setattr(repositories, "pg_fetch", fake)
    repositories.get_competition_radar(limit=11)

    assert "limit %s" in seen["sql"]
    assert seen["params"] == (11,)
