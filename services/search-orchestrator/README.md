# Search Orchestrator Service

This directory is the runtime stub for federated Sherlock search on the platform side.

## Service purpose

The search orchestrator is responsible for accepting Sherlock search requests and returning normalized result objects for workspace/cloud search.

It should eventually:
- accept a Sherlock query object
- query platform workspace indexes
- normalize and return result objects
- preserve permission boundaries and provenance
- expose source markers so higher-level fusion can combine platform results with Lampstand and memory results

## Backing contracts

- `schemas/search/sherlock_search_request.schema.json`
- `schemas/search/sherlock_search_result.schema.json`
- `SocioProphet/alexandrian-academy` `LearningSearchRecord`
- `SocioProphet/policy-fabric` Academy search visibility request and decision contracts

## Cross-repo boundaries

- workspace/product semantics live in `SocioProphet/prophet-workspace`
- local desktop indexing remains in `SocioProphet/lampstand`
- memory recall remains in `SocioProphet/memory-mesh`
- ontology/alignment remains in `SocioProphet/ontogenesis`
- Academy learning-loop explanation ownership remains in `SocioProphet/alexandrian-academy`
- Academy visibility decisions are governed by `SocioProphet/policy-fabric`

## Academy bridge modes

Academy search-record storage is selected by environment variable. The default remains in-memory and has no persistence side effect.

| Mode | Environment variable | Behavior |
| --- | --- | --- |
| in-memory | none | Process-local Academy records only. |
| json-file | `SEARCH_ORCHESTRATOR_ACADEMY_STORE` | Stores all Academy records in one JSON array file. |
| lampstand-jsonl | `SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_JSONL` | Stores Academy records as one JSONL file for Lampstand-style indexing. |
| lampstand-carrier | `SEARCH_ORCHESTRATOR_ACADEMY_LAMPSTAND_CARRIER_DIR` | Materializes records as carrier payloads and uses Lampstand `ingest_path` to emit payload, event, receipt, catalog, and publication-request artifacts. |

Academy visibility is policy-gated. By default, the service uses the local fallback evaluator. If `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT` is set, the service posts Policy Fabric-shaped Academy visibility requests to that endpoint and falls back to local evaluation on timeout or failure.

| Variable | Purpose |
| --- | --- |
| `SEARCH_ORCHESTRATOR_POLICY_FABRIC_ENDPOINT` | Optional explicit Policy Fabric decision endpoint. |
| `SEARCH_ORCHESTRATOR_POLICY_FABRIC_TIMEOUT_SECONDS` | Optional timeout in seconds; default is `2.0`. |

The live Policy Fabric adapter is endpoint-explicit. No endpoint is called unless configured.

## Runtime introspection

`GET /v1/search/debug/config` returns non-secret runtime mode information:

- active Academy repository mode;
- which storage modes are configured as booleans;
- current Academy record count;
- active Academy policy evaluator mode;
- whether a Policy Fabric endpoint is configured, without returning the endpoint URL;
- timeout value.

The debug endpoint deliberately does not return paths, URLs, or secrets.

## First implementation posture

The first implementation should be narrow and inspectable:
- one request shape
- one result shape
- one platform-side execution seam
- explicit Academy bridge modes
- safe runtime introspection without secret disclosure
