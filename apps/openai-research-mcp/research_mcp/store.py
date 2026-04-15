from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from .errors import DocumentNotFoundError, InvalidInputError
from .models import AuthContext, Document


def validate_canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidInputError(f"invalid canonical url: {url}")
    return parsed._replace(fragment="").geturl()


def load_documents_from_json(path: Path) -> list[Document]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Document(
            id=str(item["id"]),
            title=str(item["title"]),
            text=str(item.get("text", "")),
            url=validate_canonical_url(str(item["url"])),
            metadata=dict(item.get("metadata", {})),
            allowed_organizations=tuple(item.get("allowed_organizations", [])),
            allowed_subjects=tuple(item.get("allowed_subjects", [])),
            tags=tuple(item.get("tags", [])),
        )
        for item in data
    ]


class InMemoryDocumentBackend:
    def __init__(self, documents: list[Document]):
        self.documents = list(documents)
        self.by_id = {doc.id: doc for doc in self.documents}

    def visible_documents(self, ctx: AuthContext) -> list[Document]:
        return [doc for doc in self.documents if doc.is_visible_to(ctx)]

    def search(self, query: str, *, limit: int, auth_context: AuthContext) -> list[Document]:
        q = query.strip().casefold()
        if not q:
            return []
        scored = []
        for doc in self.visible_documents(auth_context):
            hay = "{}\n{}\n{}".format(doc.title, doc.text, " ".join(doc.tags)).casefold()
            score = hay.count(q) or sum(1 for token in q.split() if token and token in hay)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda item: (-item[0], item[1].title, item[1].id))
        return [doc for _, doc in scored[:limit]]

    def fetch(self, document_id: str, *, auth_context: AuthContext) -> Document:
        if document_id not in self.by_id:
            raise DocumentNotFoundError()
        doc = self.by_id[document_id]
        if not doc.is_visible_to(auth_context):
            raise DocumentNotFoundError()
        return doc
