from __future__ import annotations

from .db import ch_query, pg_fetch


def get_frontier_provenance(limit: int = 50):
    sql = """
        select model_release_id,
               groupUniqArray(source_trust_class) as source_trust_classes,
               min(freshness_days) as min_freshness_days,
               max(freshness_days) as max_freshness_days,
               sum(reproduced_by_us) as reproduced_fact_count,
               count() as metric_fact_count
        from metric_facts
        group by model_release_id
        order by model_release_id asc
        limit {limit:UInt64}
    """
    return ch_query(sql, {"limit": int(limit)})


def get_reproduced_vs_claimed(limit: int = 50):
    rows = pg_fetch(
        """
        select cs.competitor_snapshot_id,
               cs.provider_id,
               cs.model_release_id,
               cs.reproduced_by_us,
               cs.freshness_days,
               cs.source_trust_class,
               cs.strategic_relevance,
               sd.name as source_name,
               sd.methodology_snapshot_hash,
               count(mc.metric_crosswalk_id) as crosswalk_count
        from competitor_snapshots cs
        join source_descriptors sd
          on sd.source_descriptor_id = cs.source_descriptor_id
        left join metric_crosswalks mc
          on mc.source_descriptor_id = cs.source_descriptor_id
        group by cs.competitor_snapshot_id, cs.provider_id, cs.model_release_id,
                 cs.reproduced_by_us, cs.freshness_days, cs.source_trust_class,
                 cs.strategic_relevance, sd.name, sd.methodology_snapshot_hash
        order by cs.strategic_relevance desc, cs.freshness_days asc, cs.snapshot_ts desc
        limit %s
        """,
        (int(limit),),
    )
    for row in rows:
        row["coverage_state"] = "reproduced" if row["reproduced_by_us"] else "claimed_only"
    return rows
