from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from . import config
from .homeserver import MatrixClient
from .router import route_event

logger = logging.getLogger(__name__)

app = FastAPI(title="Matrix Shell Integration", version="0.1.0")

_matrix_client = MatrixClient()


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"status": "ok", "service": "matrix-shell-integration"}


@app.put("/transactions/{txn_id}")
async def handle_transaction(
    txn_id: str,
    body: dict[str, Any],
    authorization: str = Header(...),
) -> dict[str, Any]:
    """Matrix homeserver pushes appservice transactions here.

    Authentication: the homeserver sends ``Authorization: Bearer <hs_token>``.
    We verify it matches our configured HS_TOKEN before processing.
    """
    expected = f"Bearer {config.HS_TOKEN}"
    if not config.HS_TOKEN or authorization != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    events: list[dict[str, Any]] = body.get("events", [])
    for event in events:
        try:
            await route_event(event, _matrix_client)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unhandled error routing event %s: %s", event.get("event_id"), exc)

    # Matrix appservice protocol requires an empty JSON object on success
    return {}


@app.get("/_matrix/app/v1/users/{user_id:path}")
async def query_user(user_id: str) -> dict[str, Any]:
    """Required by the appservice protocol.

    Return 200 for users we manage (our bot user), 404 otherwise.
    Synapse sends the full MXID without the leading ``@``, so we normalise.
    """
    mxid = user_id if user_id.startswith("@") else f"@{user_id}"
    if mxid == config.BOT_USER_ID:
        return {}
    raise HTTPException(status_code=404, detail="user not found")
