# Backend adapter notes

The production seam is the retrieval backend.

Minimum contract:
- `search(query, limit, auth_context) -> list[Document]`
- `fetch(document_id, auth_context) -> Document`

If an internal retrieval service already exists, keep the response shapes stable and preserve canonical URLs exactly across search, fetch, audit, and export.
