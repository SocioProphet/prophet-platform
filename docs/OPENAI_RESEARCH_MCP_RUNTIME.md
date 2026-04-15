# OpenAI research MCP runtime lane

`apps/openai-research-mcp/` is the Prophet Platform runtime starter for a deep-research-compatible remote MCP service.

Why it belongs here:

- it is a deployable runtime surface, not a standards-only repository concern
- it mirrors the platform rule that deployable services belong under `apps/`
- it keeps the read-only `search` / `fetch` research plane separate from export handoff

Operational rule:

1. retrieval stays read-only
2. artifact export is separately authorized
3. browser/widget payloads do not receive raw local filesystem paths
