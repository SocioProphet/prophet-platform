"""OpenInference-conventioned tracing seam for prophet-platform services.

This is a *thin* seam: one call (`reasoning_span(...)`) emits an
OpenInference-conventioned OTel span and stamps the reasoning-run id
(``correlation_id`` in the evidence fabric) onto it, so a live trace can be
correlated back to the durable ReasoningRun / EvidenceReceipt evidence.

Design rules (see docs/OBSERVABILITY_OTEL_OPENINFERENCE.md):

* Spans are the *live trace*. Receipts (``app/receipts.py``) are the *durable
  evidence*. This seam does NOT replace receipts and does NOT emit them.
* The binding key is ``correlation_id`` (== reasoning-run id). It is stamped on
  every span as the ``prophet.reasoning_run.id`` attribute. Emit the receipt with
  the *same* ``correlation_id`` and the span and the receipt line up.
* Backend-free and dependency-optional. If the OpenTelemetry SDK is not
  installed, or ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset, this degrades to a
  no-op context manager — importing and calling it is always safe.

Turn it on per service by installing the OTel SDK and setting:

    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318   # in-cluster / compose
    OTEL_SERVICE_NAME=eval-fabric-api                         # optional, recommended
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import Iterator
from typing import Any

# --- OpenInference span kinds for prophet-platform AI operations -------------
# These map 1:1 to the lifecycle stages defined in the conventions doc.
DISCOVERY = "discovery"
RETRIEVAL = "retrieval"
PLANNING = "planning"
TOOL_CALL = "tool_call"
APPROVAL = "approval"       # approval / gate (channel + autonomy gates)
SIDE_EFFECT = "side_effect"

_SPAN_KINDS = {DISCOVERY, RETRIEVAL, PLANNING, TOOL_CALL, APPROVAL, SIDE_EFFECT}

# Attribute keys (stable; consumed by the conventions doc and downstream tooling).
ATTR_SPAN_KIND = "openinference.span.kind"
ATTR_REASONING_RUN_ID = "prophet.reasoning_run.id"
ATTR_RECEIPT_REF = "prophet.receipt.ref"
ATTR_SERVICE_REF = "prophet.service.ref"

SERVICE_REF = "apps/eval-fabric-api"


def _tracer() -> Any | None:
    """Return an OTel tracer, or None if tracing is unavailable / disabled.

    Tracing is considered *off* unless an OTLP endpoint is configured. This keeps
    the seam inert by default and avoids surprising network calls.
    """
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return None
    try:  # opentelemetry-sdk is an optional dependency
        from opentelemetry import trace  # type: ignore
    except Exception:
        return None
    return trace.get_tracer("prophet-platform.openinference")


@contextlib.contextmanager
def reasoning_span(
    name: str,
    *,
    span_kind: str,
    correlation_id: str | None = None,
    receipt_ref: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Iterator[str]:
    """Emit one OpenInference-conventioned span bound to a reasoning run.

    Args:
        name: Human span name, e.g. "retrieve_evidence".
        span_kind: One of the module constants (DISCOVERY, RETRIEVAL, PLANNING,
            TOOL_CALL, APPROVAL, SIDE_EFFECT).
        correlation_id: The reasoning-run id. If omitted, one is generated and
            yielded so the caller can pass the SAME value to the receipt emitter.
        receipt_ref: Optional durable-evidence pointer (e.g. "receipt://<id>")
            to cross-link the live span to its receipt.
        attributes: Extra span attributes (must follow plane field-class rules —
            no raw prompt/assistant content on analytics-bound spans).

    Yields:
        The ``correlation_id`` used — pass it straight into
        ``receipts.emit_artifacts(correlation_id=...)`` to bind span -> receipt.
    """
    if span_kind not in _SPAN_KINDS:
        raise ValueError(f"unknown span_kind {span_kind!r}; expected one of {sorted(_SPAN_KINDS)}")

    correlation_id = correlation_id or str(uuid.uuid4())
    tracer = _tracer()

    if tracer is None:
        # No-op path: still yield the correlation_id so callers behave identically
        # whether or not tracing is wired.
        yield correlation_id
        return

    span_attrs: dict[str, Any] = {
        ATTR_SPAN_KIND: span_kind,
        ATTR_REASONING_RUN_ID: correlation_id,
        ATTR_SERVICE_REF: SERVICE_REF,
    }
    if receipt_ref:
        span_attrs[ATTR_RECEIPT_REF] = receipt_ref
    if attributes:
        span_attrs.update(attributes)

    with tracer.start_as_current_span(name, attributes=span_attrs):
        yield correlation_id
