"""Teeth for the DataCite client + concept/version DOI pairing (Lever A).

Proven BOTH ways (a control that fires):
  1. minting with an UNREGISTERED / placeholder prefix FAILS (no network call);
  2. minting without a valid IMMUTABLE artifact ref (bad digest / bad receipt) FAILS;
  3. a valid deposition PASSES and yields a RESOLVABLE concept + version PAIR,
     with the version DOI linked back to the concept (IsVersionOf) and the
     concept linked forward (HasVersion) — all against a faithful in-process
     DataCite REST mock (httpx.MockTransport), never a hardcoded prefix.

The mock speaks the DataCite JSON:API contract (POST /dois, GET /dois/{doi})
so the client's real HTTP code path is exercised end-to-end.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from lattice_studio.datacite import (
    DataCiteClient,
    DataCiteConfig,
    DataCiteError,
    ImmutableArtifactRef,
    PLACEHOLDER_PREFIXES,
)

GOOD_DIGEST = "sha256:" + "a" * 64
GOOD_RECEIPT = "sha256:" + "b" * 64
REGISTERED_PREFIX = "10.71234"  # stand-in for a really-registered prefix (supplied via config, not hardcoded in src)


def _artifact(digest: str = GOOD_DIGEST, receipt: str = GOOD_RECEIPT, storage: str = "zot") -> ImmutableArtifactRef:
    return ImmutableArtifactRef(
        storage=storage,
        locator="zot.internal/lattice/demo-csv@" + digest,
        digest=digest,
        receipt_sha256=receipt,
        media_type="text/csv",
        size_bytes=1234,
    )


def _fake_datacite() -> httpx.MockTransport:
    """A faithful in-memory DataCite REST endpoint (JSON:API)."""
    store: dict[str, dict] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # auth must be present — mirrors the real API rejecting anonymous deposits
        if "authorization" not in {k.lower() for k in request.headers}:
            return httpx.Response(401, json={"errors": [{"title": "unauthorized"}]})
        if request.method == "POST" and request.url.path == "/dois":
            body = json.loads(request.content)
            attrs = body["data"]["attributes"]
            doi = attrs["doi"]
            state = "findable" if attrs.get("event") == "publish" else "draft"
            attrs = {**attrs, "state": state}
            store[doi] = {"data": {"id": doi, "type": "dois", "attributes": attrs}}
            return httpx.Response(201, json=store[doi])
        if request.method == "GET" and request.url.path.startswith("/dois/"):
            doi = request.url.path[len("/dois/"):]
            if doi in store:
                return httpx.Response(200, json=store[doi])
            return httpx.Response(404, json={"errors": [{"title": "not found"}]})
        return httpx.Response(400, json={"errors": [{"title": "bad request"}]})

    return httpx.MockTransport(handler)


def _client(prefix: str = REGISTERED_PREFIX) -> DataCiteClient:
    cfg = DataCiteConfig(
        api_base="https://api.test.datacite.org",
        prefix=prefix,
        repository_id="SPKC.LATTICE",
        password="secret-from-k8s",
    )
    return DataCiteClient(config=cfg, transport=_fake_datacite())


# ── TEETH 1: unregistered / placeholder prefix is REJECTED before any network call ──
def test_mint_without_registered_prefix_fails():
    for bad in ("", *sorted(PLACEHOLDER_PREFIXES), "not-a-prefix"):
        client = _client(prefix=bad)
        with pytest.raises(DataCiteError):
            asyncio.run(
                client.mint_concept_doi(
                    kind="dataset", title="Demo CSV", creators=["SocioProphet"],
                    artifact=_artifact(), concept_key="demo-csv",
                )
            )


# ── TEETH 2: a DOI with no valid immutable artifact ref is REJECTED ──
def test_mint_without_immutable_artifact_ref_fails():
    client = _client()
    # bad content digest
    with pytest.raises(DataCiteError):
        asyncio.run(
            client.mint_concept_doi(
                kind="dataset", title="Demo CSV", creators=["SocioProphet"],
                artifact=_artifact(digest="not-content-addressed"), concept_key="demo-csv",
            )
        )
    # missing SHA-256 receipt binding
    with pytest.raises(DataCiteError):
        asyncio.run(
            client.mint_concept_doi(
                kind="dataset", title="Demo CSV", creators=["SocioProphet"],
                artifact=_artifact(receipt="nope"), concept_key="demo-csv",
            )
        )


# ── TEETH 3: a valid deposition PASSES with a resolvable concept + version PAIR ──
def test_valid_deposition_passes_with_resolvable_concept_version_pair():
    client = _client()
    pair = asyncio.run(
        client.mint_concept_and_version(
            kind="dataset", title="Demo CSV Dataset", creators=["SocioProphet"],
            concept_key="demo-csv", version="1.0.0",
            concept_artifact=_artifact(digest="sha256:" + "c" * 64),
            version_artifact=_artifact(digest="sha256:" + "d" * 64),
        )
    )
    concept, version = pair["concept"], pair["version"]

    # both DOIs are minted under the registered prefix and are distinct
    assert concept.doi.startswith(REGISTERED_PREFIX + "/")
    assert version.doi.startswith(REGISTERED_PREFIX + "/")
    assert concept.doi != version.doi
    assert concept.is_concept and not version.is_concept
    assert version.version == "1.0.0"

    # both are findable (published) and resolvable back through the API
    assert concept.state == "findable" and version.state == "findable"
    got_concept = asyncio.run(client.get_doi(concept.doi))
    got_version = asyncio.run(client.get_doi(version.doi))
    assert got_concept is not None and got_version is not None

    # the version DOI links to the concept (IsVersionOf) ...
    v_rels = got_version["data"]["attributes"]["relatedIdentifiers"]
    assert any(r["relationType"] == "IsVersionOf" and r["relatedIdentifier"] == concept.doi for r in v_rels)
    # ... and binds the immutable content digest
    assert any(r["relationType"] == "IsIdenticalTo" and r["relatedIdentifier"].startswith("sha256:") for r in v_rels)

    # the concept DOI back-links to the version (HasVersion)
    c_rels = got_concept["data"]["attributes"]["relatedIdentifiers"]
    assert any(r["relationType"] == "HasVersion" and r["relatedIdentifier"] == version.doi for r in c_rels)

    # every minted DOI carries its SHA-256 receipt + content digest
    assert version.receipt_sha256 == GOOD_RECEIPT
    assert version.artifact_digest == "sha256:" + "d" * 64
