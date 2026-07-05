from __future__ import annotations

from .db import pg_fetch


def get_run_provenance(run_id: str):
    run_rows = pg_fetch(
        """
        select run_id, run_type, status, started_at, completed_at,
               provider_id, model_release_id, source_descriptor_id,
               seed_policy, reproducibility_mode
        from eval_runs
        where run_id = %s
        """,
        (run_id,),
    )
    repro_rows = pg_fetch(
        """
        select repro_ledger_entry_id, run_id, prompt_pack_id,
               fixture_snapshot_id, tool_bundle_id, seed_policy,
               environment_hash, methodology_snapshot_hash,
               replay_artifact_id, notes
        from repro_ledger_entries
        where run_id = %s
        order by created_at desc
        """,
        (run_id,),
    )
    methodology_rows = pg_fetch(
        """
        select ms.methodology_snapshot_id, ms.source_descriptor_id,
               ms.hash, ms.captured_at, ms.url, ms.notes
        from methodology_snapshots ms
        join repro_ledger_entries rle
          on rle.methodology_snapshot_hash = ms.hash
        where rle.run_id = %s
        order by ms.captured_at desc
        """,
        (run_id,),
    )
    return {
        "run": run_rows[0] if run_rows else None,
        "repro_ledger_entries": repro_rows,
        "methodology_snapshots": methodology_rows,
    }


def get_model_attribution(subject_id: str, window: str = "rolling_30d"):
    rows = pg_fetch(
        """
        select causal_attribution_id, subject_id, "window", attributions, notes
        from causal_attributions
        where subject_id = %s and "window" = %s
        order by created_at desc
        limit 1
        """,
        (subject_id, window),
    )
    return rows[0] if rows else None


def get_model_repro_entries(model_release_id: str):
    return pg_fetch(
        """
        select rle.repro_ledger_entry_id, rle.run_id, rle.prompt_pack_id,
               rle.fixture_snapshot_id, rle.tool_bundle_id,
               rle.seed_policy, rle.environment_hash,
               rle.methodology_snapshot_hash, rle.replay_artifact_id,
               rle.notes
        from repro_ledger_entries rle
        join eval_runs er on er.run_id = rle.run_id
        where er.model_release_id = %s
        order by rle.created_at desc
        """,
        (model_release_id,),
    )


def get_metric_crosswalks(limit: int = 50):
    return pg_fetch(
        """
        select metric_crosswalk_id, source_descriptor_id, source_metric_name,
               canonical_metric_definition_id, transform_notes
        from metric_crosswalks
        order by created_at desc
        limit %s
        """,
        (int(limit),),
    )
