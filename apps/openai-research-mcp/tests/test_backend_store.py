from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_mcp.errors import DocumentNotFoundError, InvalidInputError
from research_mcp.models import AuthContext, Document
from research_mcp.store import InMemoryDocumentBackend, load_documents_from_json, validate_canonical_url


class BackendStoreTests(unittest.TestCase):
    def test_validate_canonical_url_strips_fragments(self):
        self.assertEqual(
            validate_canonical_url("https://example.com/docs/item#section"),
            "https://example.com/docs/item",
        )

    def test_validate_canonical_url_rejects_relative_urls(self):
        with self.assertRaises(InvalidInputError):
            validate_canonical_url("/not/a/canonical/url")

    def test_load_documents_from_json_normalizes_visibility_and_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "documents.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "doc-1",
                            "title": "Example",
                            "text": "Body",
                            "url": "https://example.com/doc#ignored",
                            "allowed_organizations": ["org-a"],
                            "allowed_subjects": ["subject-a"],
                            "tags": ["alpha"],
                            "metadata": {"k": "v"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            docs = load_documents_from_json(path)

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].url, "https://example.com/doc")
        self.assertEqual(docs[0].allowed_organizations, ("org-a",))
        self.assertEqual(docs[0].allowed_subjects, ("subject-a",))
        self.assertEqual(docs[0].tags, ("alpha",))

    def test_visibility_filters_search_and_fetch(self):
        backend = InMemoryDocumentBackend(
            [
                Document(
                    id="public-doc",
                    title="Shared Canonical Doc",
                    text="canonical shared text",
                    url="https://example.com/public",
                ),
                Document(
                    id="org-doc",
                    title="Private Canonical Doc",
                    text="canonical private text",
                    url="https://example.com/private",
                    allowed_organizations=("org-a",),
                ),
            ]
        )

        anonymous = AuthContext(anonymous_read=True)
        org_a = AuthContext(subject="reader", organization="org-a", scopes=("documents:read",))

        anonymous_results = backend.search("canonical", limit=10, auth_context=anonymous)
        self.assertEqual([doc.id for doc in anonymous_results], ["public-doc"])
        with self.assertRaises(DocumentNotFoundError):
            backend.fetch("org-doc", auth_context=anonymous)

        org_results = backend.search("canonical", limit=10, auth_context=org_a)
        self.assertEqual([doc.id for doc in org_results], ["org-doc", "public-doc"])
        self.assertEqual(backend.fetch("org-doc", auth_context=org_a).id, "org-doc")

    def test_fetch_missing_document_raises_not_found(self):
        backend = InMemoryDocumentBackend([])
        with self.assertRaises(DocumentNotFoundError):
            backend.fetch("missing", auth_context=AuthContext(anonymous_read=True))

    def test_search_ranking_is_deterministic_by_score_then_title_then_id(self):
        backend = InMemoryDocumentBackend(
            [
                Document(id="b", title="Beta", text="canonical", url="https://example.com/b"),
                Document(id="a", title="Alpha", text="canonical", url="https://example.com/a"),
                Document(id="c", title="Gamma", text="canonical canonical", url="https://example.com/c"),
            ]
        )

        results = backend.search("canonical", limit=10, auth_context=AuthContext(anonymous_read=True))
        self.assertEqual([doc.id for doc in results], ["c", "a", "b"])


if __name__ == "__main__":
    unittest.main()
