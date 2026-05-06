from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .errors import BackendProtocolError, BackendUnavailableError, DocumentNotFoundError, InvalidInputError
from .models import AuthContext, Document


def validate_canonical_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise InvalidInputError(f"invalid canonical url: {url}")
    return parsed._replace(fragment="").geturl()


def _document_from_mapping(item: dict[str, Any]) -> Document:
    try:
        return Document(
            id=str(item["id"]),
            title=str(item["title"]),
            text=str(item.get("text", "")),
            url=validate_canonical_url(str(item["url"])),
            metadata=dict(item.get("metadata", {})),
            allowed_organizations=tuple(item.get("allowed_organizations", [])),
            allowed_subjects=tuple(item.get("allowed_subjects", [])),
            tags=tuple(item.get("tags", [])),
        )
    except KeyError as exc:
        raise BackendProtocolError(f"missing document field: {exc.args[0]}") from exc


def load_documents_from_json(path: Path) -> list[Document]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [_document_from_mapping(item) for item in data]


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


class HttpSearchFetchBackend:
    """Small stdlib-only adapter for an upstream search/fetch service.

    Expected upstream contract:
    - GET /search?q=<query>&limit=<n> -> {"results": [{"id", "title", "url", ...}]}
    - GET /fetch?id=<document_id> -> {"id", "title", "text", "url", ...}
    """

    def __init__(self, base_url: str, *, timeout_seconds: float = 5.0):
        self.base_url = base_url.rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidInputError("backend base_url must be an absolute HTTP(S) URL")
        self.timeout_seconds = timeout_seconds

    def _headers(self, auth_context: AuthContext) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if auth_context.subject:
            headers["X-Subject"] = auth_context.subject
        if auth_context.organization:
            headers["X-Organization"] = auth_context.organization
        if auth_context.scopes:
            headers["X-Scopes"] = " ".join(auth_context.scopes)
        return headers

    def _get_json(self, path: str, params: dict[str, str], auth_context: AuthContext) -> dict[str, Any]:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        request = Request(url, headers=self._headers(auth_context), method="GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code == 404:
                raise DocumentNotFoundError() from exc
            raise BackendUnavailableError(f"backend returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise BackendUnavailableError(str(exc.reason)) from exc
        except TimeoutError as exc:
            raise BackendUnavailableError("backend request timed out") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BackendProtocolError("backend returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise BackendProtocolError("backend JSON response must be an object")
        return payload

    def search(self, query: str, *, limit: int, auth_context: AuthContext) -> list[Document]:
        payload = self._get_json("/search", {"q": query, "limit": str(limit)}, auth_context)
        results = payload.get("results")
        if not isinstance(results, list):
            raise BackendProtocolError("search response must contain results array")
        return [_document_from_mapping(item) for item in results[:limit]]

    def fetch(self, document_id: str, *, auth_context: AuthContext) -> Document:
        payload = self._get_json("/fetch", {"id": document_id}, auth_context)
        return _document_from_mapping(payload)
