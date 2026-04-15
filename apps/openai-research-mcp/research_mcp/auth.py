from __future__ import annotations

import json
from pathlib import Path

from .errors import AuthError
from .models import AuthContext


def load_static_tokens(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("tokens", {})


class StaticTokenAuthorizer:
    def __init__(self, tokens: dict[str, dict], *, allow_anonymous_read: bool = True):
        self.tokens = tokens
        self.allow_anonymous_read = allow_anonymous_read

    def authorize_read(self, token: str | None) -> AuthContext:
        if token and token in self.tokens:
            row = self.tokens[token]
            return AuthContext(
                subject=row.get("subject"),
                organization=row.get("organization"),
                scopes=tuple(row.get("scopes", [])),
                anonymous_read=False,
            )
        if self.allow_anonymous_read:
            return AuthContext(anonymous_read=True)
        raise AuthError("missing_token")

    def authorize_export(self, token: str | None) -> AuthContext:
        if not token or token not in self.tokens:
            raise AuthError("missing_token")
        row = self.tokens[token]
        ctx = AuthContext(
            subject=row.get("subject"),
            organization=row.get("organization"),
            scopes=tuple(row.get("scopes", [])),
            anonymous_read=False,
        )
        if "artifacts:write" not in ctx.scopes:
            raise AuthError("missing_scope:artifacts:write")
        return ctx
