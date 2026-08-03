"""Real DataCite REST client + concept/version DOI pairing for Lattice Studio.

Zenodo parity (and the BEAT): every minted DOI is bound to an *immutable,
content-addressed artifact* (a zot/MinIO digest) and its SHA-256 receipt, and
each **version** gets its own DOI linked back to a **concept** DOI — the
Zenodo/DataCite versioning model (concept DOI ⇄ version DOIs), done natively.

Design constraints honoured here:
  * consume-not-fork — talks to the real DataCite REST API over ``httpx``
    (already a dependency); no vendored SDK, no CDN.
  * SHA-256 is FIPS-180-4 the *algorithm* (``hashlib.sha256``). This is NOT a
    claim of a FIPS-140 validated crypto *module*.
  * The DOI prefix and credentials are READ FROM CONFIG/SECRET — never
    hardcoded. Minting refuses to run against an unregistered placeholder
    prefix (``10.82044`` / ``10.0000`` / ``10.5072`` demo values), so the
    code path cannot silently emit fake-but-plausible DOIs.

Nothing here is *live* until a real DataCite prefix is registered (account +
fee, external/credentialed) and supplied via ``DATACITE_PREFIX``. Until then
this module runs green against the DataCite **test** API
(``https://api.test.datacite.org``) or a faithful in-process mock transport.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

# ── configuration boundary ────────────────────────────────────────────────
# Everything credentialed/external is read here. Nothing below hardcodes a
# prefix or a credential.
DATACITE_API_BASE = os.getenv("DATACITE_API_BASE", "https://api.test.datacite.org")
DATACITE_PREFIX = os.getenv("DATACITE_PREFIX", "")                 # e.g. "10.71234" (REGISTERED). Empty until registered.
DATACITE_REPOSITORY_ID = os.getenv("DATACITE_REPOSITORY_ID", "")  # DataCite repository account (username)
DATACITE_PASSWORD = os.getenv("DATACITE_PASSWORD", "")            # repository password / secret
# Resolver base used inside the DataCite `url` attribute (the landing target).
DATACITE_RESOLVE_BASE = os.getenv("STUDIO_RESOLVE_BASE", "https://studio.socioprophet.ai/resolve")

# Prefixes that DataCite / IANA reserve for tests & demos, plus our own
# pre-registration placeholders. Minting a REAL deposition against any of these
# is refused: they never resolve at doi.org.
PLACEHOLDER_PREFIXES = frozenset({"10.82044", "10.0000", "10.5072"})

_PREFIX_RE = re.compile(r"^10\.\d{4,9}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DataCiteError(RuntimeError):
    """Raised when a deposition cannot be made valid — before any network call."""


@dataclass(frozen=True)
class ImmutableArtifactRef:
    """A pointer to content-addressed immutable storage (zot OCI or workspace-MinIO).

    ``digest`` is the authoritative SHA-256 content address (``sha256:<64 hex>``).
    ``receipt_sha256`` is the SHA-256 of the receipt that attests the deposition
    (hash-chained receipt-gateway record, canonical-JSON). Both are required —
    a DOI that does not bind to immutable bytes is not a citable identity.
    """

    storage: str            # "zot" | "workspace-minio"
    locator: str            # OCI ref or s3 URI, e.g. "zot.internal/lattice/demo-csv@sha256:..."
    digest: str             # "sha256:<64 hex>"  — content address (FIPS-180-4 algorithm)
    receipt_sha256: str     # "sha256:<64 hex>"  — SHA-256 of the deposition receipt
    media_type: str = "application/octet-stream"
    size_bytes: int | None = None

    def validate(self) -> None:
        if not self.locator:
            raise DataCiteError("immutable artifact ref: locator is required")
        if not _SHA256_RE.match(self.digest or ""):
            raise DataCiteError(f"immutable artifact ref: digest must be 'sha256:<64 hex>', got {self.digest!r}")
        if not _SHA256_RE.match(self.receipt_sha256 or ""):
            raise DataCiteError(
                f"immutable artifact ref: receipt_sha256 must be 'sha256:<64 hex>', got {self.receipt_sha256!r}"
            )
        if self.storage not in ("zot", "workspace-minio"):
            raise DataCiteError(f"immutable artifact ref: unknown storage backend {self.storage!r}")

    def to_related_identifiers(self, concept_doi: str | None) -> list[dict[str, Any]]:
        rels: list[dict[str, Any]] = [
            # bind the DOI to the immutable content address
            {"relatedIdentifier": self.digest, "relatedIdentifierType": "Handle", "relationType": "IsIdenticalTo"},
        ]
        if concept_doi:
            rels.append(
                {"relatedIdentifier": concept_doi, "relatedIdentifierType": "DOI", "relationType": "IsVersionOf"}
            )
        return rels


@dataclass
class DataCiteConfig:
    """Resolved config for a mint. Constructed from env by default; overridable in tests."""

    api_base: str = field(default_factory=lambda: DATACITE_API_BASE)
    prefix: str = field(default_factory=lambda: DATACITE_PREFIX)
    repository_id: str = field(default_factory=lambda: DATACITE_REPOSITORY_ID)
    password: str = field(default_factory=lambda: DATACITE_PASSWORD)
    resolve_base: str = field(default_factory=lambda: DATACITE_RESOLVE_BASE)

    def require_registered_prefix(self) -> str:
        """Return the prefix, or raise if it is missing/placeholder. TEETH."""
        prefix = (self.prefix or "").strip()
        if not prefix:
            raise DataCiteError(
                "DATACITE_PREFIX is not set — a real, registered DataCite prefix is required to mint. "
                "Not live until the prefix is registered (see the tracking issue)."
            )
        if prefix in PLACEHOLDER_PREFIXES:
            raise DataCiteError(
                f"DATACITE_PREFIX={prefix!r} is a placeholder/test prefix that does not resolve at doi.org. "
                "Register a real prefix and set DATACITE_PREFIX to it."
            )
        if not _PREFIX_RE.match(prefix):
            raise DataCiteError(f"DATACITE_PREFIX={prefix!r} is not a valid DOI prefix ('10.NNNN').")
        return prefix

    def require_credentials(self) -> tuple[str, str]:
        if not self.repository_id or not self.password:
            raise DataCiteError(
                "DATACITE_REPOSITORY_ID / DATACITE_PASSWORD are not set — the repository account "
                "credential (from the DataCite secret) is required to deposit."
            )
        return self.repository_id, self.password


def suffix_for(kind: str, key: str) -> str:
    """Deterministic, collision-resistant DOI suffix from a stable key (content-addressed)."""
    h = hashlib.sha256(f"{kind}:{key}".encode("utf-8")).hexdigest()
    return f"{kind}.{h[:12]}"


def _now_year() -> int:
    return datetime.now(timezone.utc).year


def _datacite_attributes(
    doi: str,
    *,
    title: str,
    creators: list[str],
    kind: str,
    artifact: ImmutableArtifactRef,
    resolve_base: str,
    concept_doi: str | None,
    version: str | None,
    is_concept: bool,
) -> dict[str, Any]:
    """Build a DataCite 4.x metadata payload. `event=publish` requests findable state."""
    resource_type = "Dataset" if kind in ("dataset", "graph", "data") else "Software" if kind in (
        "ml-model", "model", "application", "service", "notebook") else "Other"
    descr = (
        f"Proof-carrying record. content_digest={artifact.digest}; "
        f"receipt_sha256={artifact.receipt_sha256}; storage={artifact.storage}; "
        f"locator={artifact.locator}. Integrity: SHA-256 (FIPS-180-4 algorithm)."
    )
    attrs: dict[str, Any] = {
        "doi": doi,
        "prefix": doi.split("/", 1)[0],
        "titles": [{"title": title}],
        "creators": [{"name": c} for c in creators],
        "publisher": "SocioProphet Knowledge Commons",
        "publicationYear": _now_year(),
        "types": {"resourceTypeGeneral": resource_type},
        "url": f"{resolve_base}?doi={doi}",
        "descriptions": [{"descriptionType": "Other", "description": descr}],
        "relatedIdentifiers": artifact.to_related_identifiers(None if is_concept else concept_doi),
        "event": "publish",
    }
    if version and not is_concept:
        attrs["version"] = version
    return attrs


@dataclass(frozen=True)
class MintedDOI:
    doi: str
    url: str
    state: str            # "findable" | "draft" | "registered"
    kind: str
    is_concept: bool
    version: str | None
    concept_doi: str | None
    artifact_digest: str
    receipt_sha256: str
    attributes: dict[str, Any]

    def resolver_url(self) -> str:
        return f"https://doi.org/{self.doi}"


class DataCiteClient:
    """Thin async DataCite REST client.

    Pass a custom ``transport`` (e.g. ``httpx.MockTransport``) to run against a
    faithful in-process mock; pass none to talk to the real API in ``api_base``.
    """

    def __init__(self, config: DataCiteConfig | None = None, transport: httpx.BaseTransport | None = None):
        self.config = config or DataCiteConfig()
        self._transport = transport

    def _auth_header(self) -> dict[str, str]:
        rid, pw = self.config.require_credentials()
        token = base64.b64encode(f"{rid}:{pw}".encode("utf-8")).decode("ascii")
        return {"Authorization": f"Basic {token}", "Content-Type": "application/vnd.api+json"}

    async def _post_doi(self, attributes: dict[str, Any]) -> dict[str, Any]:
        body = {"data": {"type": "dois", "attributes": attributes}}
        async with httpx.AsyncClient(
            base_url=self.config.api_base, transport=self._transport, timeout=30.0
        ) as client:
            resp = await client.post("/dois", headers=self._auth_header(), content=json.dumps(body))
        if resp.status_code not in (200, 201):
            raise DataCiteError(f"DataCite POST /dois failed: {resp.status_code} {resp.text[:400]}")
        return resp.json()

    async def get_doi(self, doi: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(
            base_url=self.config.api_base, transport=self._transport, timeout=30.0
        ) as client:
            resp = await client.get(f"/dois/{doi}", headers=self._auth_header())
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            raise DataCiteError(f"DataCite GET /dois/{doi} failed: {resp.status_code} {resp.text[:400]}")
        return resp.json()

    async def _mint(
        self,
        *,
        kind: str,
        title: str,
        creators: list[str],
        artifact: ImmutableArtifactRef,
        concept_doi: str | None,
        version: str | None,
        is_concept: bool,
        suffix_key: str,
    ) -> MintedDOI:
        # TEETH, before any network call: registered prefix + valid immutable artifact.
        prefix = self.config.require_registered_prefix()
        artifact.validate()
        doi = f"{prefix}/{suffix_for(kind, suffix_key)}"
        attrs = _datacite_attributes(
            doi, title=title, creators=creators or ["SocioProphet Knowledge Commons"], kind=kind,
            artifact=artifact, resolve_base=self.config.resolve_base, concept_doi=concept_doi,
            version=version, is_concept=is_concept,
        )
        result = await self._post_doi(attrs)
        state = ((result.get("data") or {}).get("attributes") or {}).get("state", "findable")
        return MintedDOI(
            doi=doi, url=attrs["url"], state=state, kind=kind, is_concept=is_concept,
            version=version, concept_doi=concept_doi, artifact_digest=artifact.digest,
            receipt_sha256=artifact.receipt_sha256, attributes=attrs,
        )

    async def mint_concept_doi(
        self, *, kind: str, title: str, creators: list[str], artifact: ImmutableArtifactRef, concept_key: str
    ) -> MintedDOI:
        """Mint the stable *concept* DOI — the identity that always points at the latest version."""
        return await self._mint(
            kind=kind, title=title, creators=creators, artifact=artifact, concept_doi=None,
            version=None, is_concept=True, suffix_key=f"concept:{concept_key}",
        )

    async def mint_version_doi(
        self, *, kind: str, title: str, creators: list[str], artifact: ImmutableArtifactRef,
        concept_doi: str, version: str, concept_key: str,
    ) -> MintedDOI:
        """Mint a *version* DOI bound to a specific immutable artifact, linked to its concept DOI."""
        if not concept_doi:
            raise DataCiteError("mint_version_doi requires a concept_doi to link against")
        return await self._mint(
            kind=kind, title=title, creators=creators, artifact=artifact, concept_doi=concept_doi,
            version=version, is_concept=False, suffix_key=f"{concept_key}:{version}",
        )

    async def mint_concept_and_version(
        self, *, kind: str, title: str, creators: list[str], concept_key: str, version: str,
        concept_artifact: ImmutableArtifactRef, version_artifact: ImmutableArtifactRef,
    ) -> dict[str, MintedDOI]:
        """Mint a resolvable concept+version PAIR in one call and return both.

        The version DOI carries ``IsVersionOf`` → concept; the concept DOI is
        updated (best-effort) with ``HasVersion`` → version so the pairing is
        navigable in both directions.
        """
        concept = await self.mint_concept_doi(
            kind=kind, title=title, creators=creators, artifact=concept_artifact, concept_key=concept_key
        )
        version_doi = await self.mint_version_doi(
            kind=kind, title=title, creators=creators, artifact=version_artifact,
            concept_doi=concept.doi, version=version, concept_key=concept_key,
        )
        # best-effort back-link concept → version (HasVersion)
        try:
            back = dict(concept.attributes)
            rels = list(back.get("relatedIdentifiers") or [])
            rels.append(
                {"relatedIdentifier": version_doi.doi, "relatedIdentifierType": "DOI", "relationType": "HasVersion"}
            )
            back["relatedIdentifiers"] = rels
            await self._post_doi(back)
        except DataCiteError:
            pass  # pairing is still valid via the version→concept link
        return {"concept": concept, "version": version_doi}
