# WOPI Host Service

This directory contains the first narrow runtime smoke for the SourceOS office cloud-suite WOPI host.

## Service purpose

The WOPI host is responsible for the document/editor boundary used by the open office suite.

It is not the total office product. It is the runtime seam that lets editor sessions interact with platform-owned document, session, version, lock, and writeback records.

## Implemented smoke responsibilities

- document-scoped file info retrieval
- payload read/write roundtrip
- lock acquisition
- lock refresh
- unlock/release
- writeback version emission
- file-backed writeback smoke
- payload metadata
- document summary
- runtime record projection for:
  - `office_document_record`
  - `office_session_record`
  - `office_version_record`
  - `office_writeback_record`

## Backing contracts

- `schemas/office/office_document_record.schema.json`
- `schemas/office/office_session_record.schema.json`
- `schemas/office/office_version_record.schema.json`
- `schemas/office/office_writeback_record.schema.json`
- `schemas/office/office_policy_decision_record.schema.json`
- `schemas/office/office_adapter_profile.schema.json`

## Contract validation

The WOPI host smoke tests validate emitted runtime records against the platform schemas.

```bash
python -m pip install fastapi==0.115.0 httpx==0.27.2 pytest jsonschema
pytest -q services/wopi-host/tests
```

The dedicated GitHub workflow is `.github/workflows/wopi-host-validation.yml`.

## Cross-repo boundaries

- product semantics live in `SocioProphet/prophet-workspace`
- runtime records and service seams live in `SocioProphet/prophet-platform`
- Linux/desktop handoff lives in SourceOS host surfaces such as `SourceOS-Linux/sourceos-shell`, `SourceOS-Linux/sourceos-devtools`, `SourceOS-Linux/TurtleTerm`, and `SourceOS-Linux/BearBrowser`
- local memory/search/ontology dependencies stay outside the hot path of editor RPC handling
- closed-provider migration/import/export evidence belongs in Exodus-style migration flows, not in WOPI runtime authority

## First implementation posture

The implementation remains intentionally narrow and testable:

- one open editor binding: Collabora-style browser editor path
- one storage backend seam for payload/file-backed smoke
- explicit lock semantics
- explicit version and writeback records
- explicit health and smoke surfaces
- no Google/Microsoft runtime dependency
- no memory or semantic graph mutation inside the critical save path
