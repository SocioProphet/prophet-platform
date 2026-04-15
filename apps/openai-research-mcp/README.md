# openai-research-mcp

Runtime starter for a deep-research-compatible remote MCP service on Prophet Platform.

This lane intentionally keeps **retrieval** separate from **artifact export**:

- `search` and `fetch` are the MCP-facing read-only contract
- artifact export is a separate handoff path that requires `artifacts:write`
- public artifact payloads expose `artifact_id`, `object_key`, and optional `download_url`, not raw local paths

## Layout

- `research_mcp/` — auth, retrieval, audit, artifact, and service orchestration
- `server.py` — local CLI demos and small HTTP validation surface
- `config/` — example token and OpenAI-facing configuration
- `data/` — example fixture corpus
- `tests/` — smoke and service tests
- `scripts/run_tests.sh` — compile + unittest
- `scripts/verify_bundle.py` — checks core files are present

## Local quickstart

```bash
export MCP_STATIC_TOKENS_FILE=config/static_tokens.example.json
python server.py verify-bundle
bash scripts/run_tests.sh
python server.py doctor
python server.py demo-search "canonical urls" --token reader-token
python server.py demo-fetch doc-citations-001 --token reader-token
python server.py demo-export --title "Sandbox report" --narrative "Narrative" --document-ids doc-citations-001 --token export-token
```
