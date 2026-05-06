from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .errors import AuthError
from .models import AuthContext


def load_static_tokens(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("tokens", {})


def _header(headers: Mapping[str, str] | None, name: str) -> str | None:
    if not headers:
        return None
    normalized = {key.lower(): value for key, value in headers.items()}
    value = normalized.get(name.lower())
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_scopes(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    normalized = raw.replace(",", " ")
    return tuple(scope for scope in normalized.split() if scope)


class StaticTokenAuthorizer:
    def __init__(self, tokens: dict[str, dict], *, allow_anonymous_read: bool = True):
        self.tokens = tokens
        self.allow_anonymous_read = allow_anonymous_read

    def authorize_read(self, token: str | None, headers: Mapping[str, str] | None = None) -> AuthContext:
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

    def authorize_export(self, token: str | None, headers: Mapping[str, str] | None = None) -> AuthContext:
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


class TrustedHeaderAuthorizer:
    """Authorizer for deployments behind an identity-validating gateway.

    This class trusts identity headers only after an external gateway has already
    authenticated the caller and stripped untrusted inbound identity headers.
    It is not safe to expose directly on the public edge without that gateway.
    """

    def __init__(
        self,
        *,
        subject_header: str = "X-Subject",
        organization_header: str = "X-Organization",
        scopes_header: str = "X-Scopes",
        allow_anonymous_read: bool = False,
        read_scope: str = "documents:read",
        export_scope: str = "artifacts:write",
    ):
        self.subject_header = subject_header
        self.organization_header = organization_header
        self.scopes_header = scopes_header
        self.allow_anonymous_read = allow_anonymous_read
        self.read_scope = read_scope
        self.export_scope = export_scope

    def _context(self, headers: Mapping[str, str] | None) -> AuthContext:
        subject = _header(headers, self.subject_header)
        organization = _header(headers, self.organization_header)
        scopes = _parse_scopes(_header(headers, self.scopes_header))
        if not subject:
            if self.allow_anonymous_read:
                return AuthContext(anonymous_read=True)
            raise AuthError("missing_trusted_subject")
        return AuthContext(subject=subject, organization=organization, scopes=scopes, anonymous_read=False)

    def authorize_read(self, token: str | None, headers: Mapping[str, str] | None = None) -> AuthContext:
        ctx = self._context(headers)
        if ctx.anonymous_read:
            return ctx
        if self.read_scope and self.read_scope not in ctx.scopes:
            raise AuthError(f"missing_scope:{self.read_scope}")
        return ctx

    def authorize_export(self, token: str | None, headers: Mapping[str, str] | None = None) -> AuthContext:
        ctx = self._context(headers)
        if ctx.anonymous_read:
            raise AuthError("missing_trusted_subject")
        if self.export_scope and self.export_scope not in ctx.scopes:
            raise AuthError(f"missing_scope:{self.export_scope}")
        return ctx
