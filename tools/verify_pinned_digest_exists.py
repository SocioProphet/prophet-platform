#!/usr/bin/env python3
"""Verify that every pinned ``@sha256:`` digest actually RESOLVES to a manifest in its
registry — INV-DEP-6, the gate that stops a freeze/promote from shipping a digest that was
never pushed.

Why this exists (the incident this closes)
------------------------------------------
A wave-deploy froze + promoted ``search-orchestrator@sha256:bbfea6e4…`` all the way through
its overlays. Every existing gate was green: the string is a legal ``<image>@sha256:<64hex>``
(INV-DEP-1 passes), it is one digest per image (INV-DEP-2 passes), the overlays render
digest-pinned (the render gate passes). But that digest is NOT a real registry manifest —
Wave 0 (the real build+push) never ran, so deploying it ``ImagePullBackOff``'d on the live
cluster. Every prior invariant checked the *shape* of the reference; none checked that the
bytes it names EXIST. This does.

  INV-DEP-6 — a digest MUST NOT be frozen or promoted unless it resolves to a manifest in the
  registry (Registry HTTP API v2 ``HEAD``/``GET .../manifests/<digest>`` returns the manifest).
  Fail-closed: ``freeze`` and ``wave-promote`` REFUSE a digest with no manifest.

Three outcomes, kept DISTINCT (so callers can tell "you shipped a fabricated digest" from
"I couldn't reach the registry to check"):

  * EXISTS      — the registry returned the manifest for that digest.               exit 0
  * ABSENT      — the registry answered and the manifest is unknown (404 /          exit 4
                  MANIFEST_UNKNOWN). This is the fabricated / never-pushed case.
  * UNREACHABLE — DNS/TLS/timeout/5xx/auth-challenge-failed: the registry could     exit 3
                  not give a definitive answer. We did not PROVE existence, so a
                  gate MUST still fail-closed — but the operator sees it is a
                  reachability problem, not a fabricated digest.

Registries supported
---------------------
  * ghcr.io                         (GitHub Container Registry)
  * registry.socioprophet.ai / zot  (the sovereign zot registry)
  * any Registry-HTTP-API-v2 host    (generic Bearer / Basic token flow)

Auth
----
Anonymous by default (public repos resolve without a token). For private repos, supply a
credential and the tool performs the standard ``WWW-Authenticate: Bearer`` token exchange:

  * ``--username`` / ``--password``    — e.g. ``x-access-token`` + ``$GITHUB_TOKEN`` in CI;
  * env ``REGISTRY_USERNAME`` / ``REGISTRY_PASSWORD`` (or ``GITHUB_ACTOR`` / ``GITHUB_TOKEN``
    for ghcr.io) are picked up automatically when the flags are absent.
  * ``--token`` supplies a ready Bearer token directly (skips the exchange).

Usage
-----
  # One reference:
  verify_pinned_digest_exists.py ref \\
      ghcr.io/socioprophet/prophet-platform/search-orchestrator@sha256:<64hex>

  # Every component in a frozen release-train manifest (the freeze/promote gate):
  verify_pinned_digest_exists.py manifest releases/manifests/release-train.<label>.manifest.json

  # Every non-example image-lock:
  verify_pinned_digest_exists.py locks 'releases/images/*.image-lock.json'
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REF_RE = re.compile(r"^(?P<registry>[^/]+)/(?P<repo>.+?)@(?P<digest>sha256:[0-9a-f]{64})$")

# The manifest media types a registry may answer with. We must Accept all of them or a
# multi-arch image (an OCI index / manifest list) HEAD can 404 under a too-narrow Accept.
_MANIFEST_ACCEPT = ", ".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.docker.distribution.manifest.v1+json",
])

# Outcome names (kept as strings so evidence records read plainly).
EXISTS = "exists"
ABSENT = "absent"
UNREACHABLE = "unreachable"

# Exit codes — DISTINCT per the incident requirement (fabricated != unreachable).
EXIT_OK = 0
EXIT_UNREACHABLE = 3
EXIT_ABSENT = 4
EXIT_USAGE = 2


@dataclass
class Result:
    status: str          # EXISTS | ABSENT | UNREACHABLE
    image: str
    digest: str
    detail: str = ""

    @property
    def ref(self) -> str:
        return f"{self.image}@{self.digest}"


# A single seam for the HTTP layer so tests can inject a fake registry without a socket.
# Returns (status_code, headers, body_bytes); raises on transport failure (DNS/TLS/timeout).
HttpFn = Callable[[str, str, dict], "tuple[int, dict, bytes]"]


def _default_http(method: str, url: str, headers: dict) -> "tuple[int, dict, bytes]":
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=_default_http.timeout) as r:  # type: ignore[attr-defined]
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        # An HTTP status IS a definitive answer from the registry (401/404/…): return it,
        # do not treat it as a transport failure.
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


_default_http.timeout = 15  # type: ignore[attr-defined]


def parse_ref(ref: str) -> "tuple[str, str, str]":
    """``registry/repo@sha256:hex`` -> (registry, repo, digest). Fail-closed on a bad ref."""
    m = REF_RE.match(ref.strip())
    if not m:
        raise SystemExit(f"::error::not a digest-pinned reference: {ref!r} "
                         f"(want <registry>/<repo>@sha256:<64hex>)")
    return m.group("registry"), m.group("repo"), m.group("digest")


def _auth_header_from_challenge(challenge: str, registry: str, repo: str,
                                username: str | None, password: str | None,
                                http: HttpFn) -> str | None:
    """Perform the Registry v2 token exchange from a ``WWW-Authenticate`` challenge.

    Returns an ``Authorization: Bearer <token>`` value, or None if we could not obtain one.
    """
    # WWW-Authenticate: Bearer realm="https://ghcr.io/token",service="ghcr.io",scope="repository:owner/name:pull"
    if not challenge.lower().startswith("bearer"):
        return None
    params: dict[str, str] = {}
    for part in re.finditer(r'(\w+)="([^"]*)"', challenge):
        params[part.group(1)] = part.group(2)
    realm = params.get("realm")
    if not realm:
        return None
    scope = params.get("scope") or f"repository:{repo}:pull"
    service = params.get("service", registry)
    url = f"{realm}?service={urllib.request.quote(service)}&scope={urllib.request.quote(scope)}"
    headers = {"Accept": "application/json"}
    # If we have creds, present them via Basic to the token endpoint (this is how a private
    # repo mints a pull-scoped Bearer token). Anonymous otherwise (public repos still work).
    if username and password:
        basic = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {basic}"
    status, _, body = http("GET", url, headers)
    if status != 200:
        return None
    try:
        data = json.loads(body.decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    token = data.get("token") or data.get("access_token")
    return f"Bearer {token}" if token else None


def _resolve_credentials(registry: str, username: str | None,
                         password: str | None) -> "tuple[str | None, str | None]":
    """Fill credentials from the environment when the flags are absent (CI convenience)."""
    if username or password:
        return username, password
    user = os.environ.get("REGISTRY_USERNAME")
    pw = os.environ.get("REGISTRY_PASSWORD")
    if user or pw:
        return user, pw
    # ghcr.io reads the standard Actions identity by default.
    if registry == "ghcr.io" and os.environ.get("GITHUB_TOKEN"):
        return os.environ.get("GITHUB_ACTOR", "x-access-token"), os.environ.get("GITHUB_TOKEN")
    return None, None


def check_manifest(image: str, digest: str, *,
                   username: str | None = None, password: str | None = None,
                   bearer: str | None = None, http: HttpFn | None = None) -> Result:
    """Resolve ``image@digest`` against its registry. Never raises for a definitive registry
    answer — only classifies EXISTS / ABSENT / UNREACHABLE."""
    http = http or _default_http
    if not DIGEST_RE.match(digest):
        raise SystemExit(f"::error::{digest!r} is not sha256:<64hex>")
    registry, _, repo = image.partition("/")
    if not repo:
        raise SystemExit(f"::error::image {image!r} has no repository path")

    scheme = "http" if (registry.startswith("localhost") or registry.startswith("127.")) else "https"
    url = f"{scheme}://{registry}/v2/{repo}/manifests/{digest}"
    headers = {"Accept": _MANIFEST_ACCEPT}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}" if not bearer.lower().startswith("bearer") else bearer

    def _classify(status: int, hdrs: dict, body: bytes) -> Result | None:
        if 200 <= status < 300:
            return Result(EXISTS, image, digest, f"registry returned manifest ({status})")
        if status == 404:
            return Result(ABSENT, image, digest,
                          "registry answered MANIFEST_UNKNOWN (404) — digest not pushed")
        return None

    try:
        status, hdrs, body = http("HEAD", url, headers)
    except Exception as exc:  # noqa: BLE001 - transport failure, not an HTTP answer
        return Result(UNREACHABLE, image, digest, f"registry unreachable: {exc!r}")

    verdict = _classify(status, hdrs, body)
    if verdict is not None:
        return verdict

    # 401/403 -> attempt the token exchange, then retry once.
    if status in (401, 403) and "www-authenticate" in hdrs:
        user, pw = _resolve_credentials(registry, username, password)
        auth = _auth_header_from_challenge(hdrs["www-authenticate"], registry, repo, user, pw, http)
        if auth:
            headers["Authorization"] = auth
            try:
                status, hdrs, body = http("HEAD", url, headers)
            except Exception as exc:  # noqa: BLE001
                return Result(UNREACHABLE, image, digest, f"registry unreachable after auth: {exc!r}")
            verdict = _classify(status, hdrs, body)
            if verdict is not None:
                return verdict
        # Could not authenticate / still ambiguous — UNREACHABLE, never a silent pass.
        return Result(UNREACHABLE, image, digest,
                      f"registry needs auth we could not satisfy (status {status})")

    # Some registries answer HEAD with 405; fall back to GET before giving up.
    if status == 405:
        try:
            status, hdrs, body = http("GET", url, headers)
        except Exception as exc:  # noqa: BLE001
            return Result(UNREACHABLE, image, digest, f"registry unreachable on GET: {exc!r}")
        verdict = _classify(status, hdrs, body)
        if verdict is not None:
            return verdict

    return Result(UNREACHABLE, image, digest, f"registry gave a non-definitive status {status}")


def check_ref(ref: str, **kw) -> Result:
    registry, repo, digest = parse_ref(ref)
    return check_manifest(f"{registry}/{repo}", digest, **kw)


def _components_from_manifest(path: Path) -> list["tuple[str, str]"]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for c in data.get("components", []):
        image = str(c.get("image", ""))
        digest = str(c.get("digest", ""))
        if image and digest:
            out.append((image, digest))
    if not out:
        raise SystemExit(f"::error::{path}: no (image, digest) components to verify")
    return out


def _components_from_locks(lock_glob: str) -> list["tuple[str, str]"]:
    out: list[tuple[str, str]] = []
    for lf in sorted(glob.glob(lock_glob)):
        if lf.endswith(".example.json"):
            continue
        lock = json.loads(Path(lf).read_text(encoding="utf-8"))
        if lock.get("status") == "example":
            continue
        image = str(lock.get("image", ""))
        digest = str(lock.get("digest", ""))
        if image and digest:
            out.append((image, digest))
    if not out:
        raise SystemExit(f"::error::no non-example locks matched {lock_glob!r} to verify")
    return out


def _verify_all(pairs: list["tuple[str, str]"], **kw) -> int:
    results = [check_manifest(img, dig, **kw) for img, dig in pairs]
    absent = [r for r in results if r.status == ABSENT]
    unreachable = [r for r in results if r.status == UNREACHABLE]
    for r in results:
        mark = {EXISTS: "OK   ", ABSENT: "ABSENT", UNREACHABLE: "UNREACH"}[r.status]
        print(f"  [{mark}] {r.ref}  — {r.detail}")
    if absent:
        print(f"::error::INV-DEP-6: {len(absent)} pinned digest(s) do NOT exist in the registry "
              f"(fabricated / never pushed). REFUSING to freeze/promote.")
        return EXIT_ABSENT
    if unreachable:
        print(f"::error::INV-DEP-6: could not PROVE existence of {len(unreachable)} digest(s) "
              f"(registry unreachable). Fail-closed: refusing to freeze/promote on unverified images.")
        return EXIT_UNREACHABLE
    print(f"OK: all {len(results)} pinned digest(s) resolve to a registry manifest (INV-DEP-6)")
    return EXIT_OK


def _common_auth_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--username", default=None, help="registry username (CI: x-access-token)")
    p.add_argument("--password", default=None, help="registry password/token (CI: $GITHUB_TOKEN)")
    p.add_argument("--token", default=None, help="ready Bearer token (skips the token exchange)")
    p.add_argument("--timeout", type=int, default=15, help="per-request timeout seconds")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("ref", help="verify a single <registry>/<repo>@sha256:<hex> reference")
    pr.add_argument("reference")
    _common_auth_args(pr)

    pm = sub.add_parser("manifest", help="verify every component in a frozen release-train manifest")
    pm.add_argument("manifest", type=Path)
    _common_auth_args(pm)

    pl = sub.add_parser("locks", help="verify every non-example image-lock in a glob")
    pl.add_argument("glob", default="releases/images/*.image-lock.json", nargs="?")
    _common_auth_args(pl)

    args = p.parse_args(argv)
    _default_http.timeout = args.timeout  # type: ignore[attr-defined]
    kw = dict(username=args.username, password=args.password, bearer=args.token)

    if args.cmd == "ref":
        r = check_ref(args.reference, **kw)
        print(f"  [{r.status.upper()}] {r.ref} — {r.detail}")
        return {EXISTS: EXIT_OK, ABSENT: EXIT_ABSENT, UNREACHABLE: EXIT_UNREACHABLE}[r.status]
    if args.cmd == "manifest":
        return _verify_all(_components_from_manifest(args.manifest), **kw)
    if args.cmd == "locks":
        return _verify_all(_components_from_locks(args.glob), **kw)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
