# Threat model

Primary boundaries:

1. browser/widget sandbox
2. research service runtime
3. artifact storage
4. upstream retrieval systems

Core rules:

- keep `search` / `fetch` read-only
- require separate authorization for export
- preserve canonical URLs across search, fetch, audit, and export
- never expose raw local paths in public artifact payloads
- treat gateway identity as authoritative when running behind a trusted proxy
