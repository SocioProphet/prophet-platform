# Artifact handoff

The runtime separates retrieval from export.

Public artifact payloads should expose:
- `artifact_id`
- `object_key`
- `sha256`
- optional `download_url`

Public artifact payloads must not expose:
- raw local filesystem paths
- private storage roots
- implicit workspace assumptions

The internal manifest may retain local operational details, but those stay behind the service boundary.
