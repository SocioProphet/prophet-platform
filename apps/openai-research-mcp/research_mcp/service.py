from __future__ import annotations

from typing import Mapping

from .audit import JsonlAuditSink
from .auth import StaticTokenAuthorizer
from .artifacts import MarkdownArtifactExporter
from .store import InMemoryDocumentBackend


class ResearchService:
    def __init__(self, *, backend: InMemoryDocumentBackend, authorizer: StaticTokenAuthorizer, audit_sink: JsonlAuditSink, exporter: MarkdownArtifactExporter):
        self.backend = backend
        self.authorizer = authorizer
        self.audit_sink = audit_sink
        self.exporter = exporter

    def search_contract(
        self,
        query: str,
        *,
        limit: int = 10,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        ctx = self.authorizer.authorize_read(token, headers=headers)
        docs = self.backend.search(query, limit=limit, auth_context=ctx)
        self.audit_sink.emit({
            "event": "search",
            "query": query,
            "limit": limit,
            "results": [d.id for d in docs],
            "organization": ctx.organization,
            "subject": ctx.subject,
        })
        return {"results": [doc.search_result() for doc in docs]}

    def fetch_contract(
        self,
        document_id: str,
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        ctx = self.authorizer.authorize_read(token, headers=headers)
        doc = self.backend.fetch(document_id, auth_context=ctx)
        self.audit_sink.emit({
            "event": "fetch",
            "document_id": document_id,
            "organization": ctx.organization,
            "subject": ctx.subject,
            "url": doc.url,
        })
        return doc.fetch_result()

    def export_report_handoff(
        self,
        title: str,
        narrative: str,
        document_ids: list[str],
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> dict:
        ctx = self.authorizer.authorize_export(token, headers=headers)
        docs = [self.backend.fetch(doc_id, auth_context=ctx).fetch_result() for doc_id in document_ids]
        payload = self.exporter.export_report(title=title, narrative=narrative, documents=docs)
        self.audit_sink.emit({
            "event": "export_report",
            "artifact_id": payload["artifact_id"],
            "document_ids": document_ids,
            "organization": ctx.organization,
            "subject": ctx.subject,
        })
        return payload
