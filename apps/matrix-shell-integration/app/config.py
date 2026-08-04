from __future__ import annotations

import os

HOMESERVER_URL: str = os.getenv("MATRIX_HOMESERVER_URL", "http://localhost:8448")
ACCESS_TOKEN: str = os.getenv("MATRIX_ACCESS_TOKEN", "")
AS_TOKEN: str = os.getenv("MATRIX_AS_TOKEN", "")
HS_TOKEN: str = os.getenv("MATRIX_HS_TOKEN", "")
BOT_USER_ID: str = os.getenv("MATRIX_BOT_USER_ID", "@sourceos-bot:localhost")
OPERATOR_URL: str = os.getenv("MATRIX_QES_OPERATOR_URL", "http://localhost:8500")
LISTEN_PORT: int = int(os.getenv("MATRIX_SHELL_INTEGRATION_PORT", "8501"))
