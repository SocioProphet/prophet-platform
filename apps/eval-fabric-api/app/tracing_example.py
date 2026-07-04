"""Usage example for the OpenInference tracing seam.

Run it standalone:

    # no-op (no endpoint set) — always works, no SDK required:
    python -m app.tracing_example

    # live trace -> local collector (needs `pip install opentelemetry-sdk
    # opentelemetry-exporter-otlp` and the collector from
    # infra/local/docker-compose.otel-collector.yml running):
    OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python -m app.tracing_example

The key pattern: the SAME ``correlation_id`` flows from the span into the
receipt emitter, so the live span (OTel) and the durable receipt (evidence
fabric) share one reasoning-run id.
"""

from __future__ import annotations

from app import tracing
from app.receipts import maybe_emit_artifacts


def run_one_retrieval(query_hash: str) -> None:
    # 1. Open an OpenInference RETRIEVAL span. We let the seam mint the
    #    reasoning-run id and yield it back to us.
    with tracing.reasoning_span(
        "retrieve_evidence",
        span_kind=tracing.RETRIEVAL,
        attributes={"prophet.query.hash": query_hash},  # no raw content
    ) as reasoning_run_id:
        # ... do the actual retrieval work here ...
        result_count = 3

        # 2. Emit the durable receipt with the SAME id -> span and receipt bind.
        #    (maybe_emit_artifacts is a no-op unless EVAL_FABRIC_EMIT_RECEIPTS=1)
        emission = maybe_emit_artifacts(
            event_type="evidence.retrieval.completed",
            action="retrieve_evidence",
            status="succeeded",
            subject_ref=f"query://{query_hash}",
            payload={"result_count": result_count},
            metrics={"result_count": result_count},
            correlation_id=reasoning_run_id,  # <-- the binding key
        )

    print(f"reasoning_run_id={reasoning_run_id}")
    if emission:
        print(f"receipt={emission.receipt_ref}")
    else:
        print("receipt=<disabled: set EVAL_FABRIC_EMIT_RECEIPTS=1>")


if __name__ == "__main__":
    run_one_retrieval(query_hash="demo-0xabc123")
