from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AuthContext:
    subject: str | None = None
    organization: str | None = None
    scopes: tuple[str, ...] = ()
    anonymous_read: bool = False

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    text: str
    url: str
    metadata: dict[str, Any] = field(default_factory=dict)
    allowed_organizations: tuple[str, ...] = ()
    allowed_subjects: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def is_visible_to(self, auth_context: AuthContext) -> bool:
        if self.allowed_organizations:
            if not auth_context.organization or auth_context.organization not in self.allowed_organizations:
                return False
        if self.allowed_subjects:
            if not auth_context.subject or auth_context.subject not in self.allowed_subjects:
                return False
        return True

    def search_result(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title, "url": self.url}

    def fetch_result(self) -> dict[str, Any]:
        out = {"id": self.id, "title": self.title, "text": self.text, "url": self.url}
        if self.metadata:
            out["metadata"] = self.metadata
        return out
