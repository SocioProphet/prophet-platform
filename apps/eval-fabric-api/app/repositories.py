from __future__ import annotations

from .db import ch_query, pg_fetch


def get_frontier(profile_id: str = "profile.high_assurance_enterprise_agent", limit: int = 20):
    sql = """
        select profile_id, subject_id, score, rank, score_policy_id
        from profile_scores
        where profile_id = {profile_id:String}
        order by rank asc, score desc
        limit {limit:UInt64}
    """
    return ch_query(sql, {"profile_id": profile_id, "limit": int(limit)})


def get_model_dossier(model_release_id: str, limit: int = 50):
    sql = """
        select metric_definition_id, value_scalar, sample_n, trial_count, ts
        from metric_facts
        where model_release_id = {model_release_id:String}
        order by ts desc
        limit {limit:UInt64}
    """
    return ch_query(sql, {"model_release_id": model_release_id, "limit": int(limit)})


def get_competition_radar(limit: int = 50):
    sql = """
        select competitor_snapshot_id, provider_id, model_release_id,
               freshness_days, source_trust_class, strategic_relevance
        from competitor_snapshots
        order by strategic_relevance desc, freshness_days asc, snapshot_ts desc
        limit %s
    """
    return pg_fetch(sql, (int(limit),))
