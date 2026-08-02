"""Prove INV-DEP-6 (the digest-exists gate) both ways, offline.

A gate that has only ever passed proves nothing. So this drives the classifier against a
FAKE registry (an injected HTTP seam — no socket) through every outcome:

  * a real digest (registry 200)            => EXISTS   (exit 0)   — a build must be reusable;
  * a fabricated digest (registry 404)      => ABSENT   (exit 4)   — the incident's placeholder;
  * a registry that raises (DNS/TLS/timeout)=> UNREACHABLE (exit 3) — DISTINCT from ABSENT, so an
                                                                      operator is never told a
                                                                      fabricated digest when the
                                                                      real problem is reachability;
  * a 401 challenge + working token exchange resolves to EXISTS/ABSENT (private-repo path);
  * a 401 we cannot satisfy                 => UNREACHABLE, never a silent pass (fail-closed).

The live ghcr proof (real oras digest passes, a fabricated one fails) is recorded in the PR;
this keeps the teeth provable with no network in CI.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "verify_pinned_digest_exists.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("verify_pinned_digest_exists", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MOD = importlib.util.module_from_spec(SPEC)
# Register before exec so the module's @dataclass can resolve its own __module__ under
# `from __future__ import annotations` (importlib does not auto-register the module name).
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)

IMAGE = "ghcr.io/socioprophet/prophet-platform/search-orchestrator"
DIGEST = "sha256:" + ("b" * 64)


def _http(responses):
    """Build a fake HTTP seam. `responses` is a list of (status, headers, body) or an
    Exception to raise, consumed in order per call."""
    calls = iter(responses)

    def fn(method, url, headers):
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        status, hdrs, body = item
        return status, hdrs, body

    return fn


# ── the two headline outcomes ──────────────────────────────────────────────────────────────

def test_real_digest_exists() -> None:
    r = MOD.check_manifest(IMAGE, DIGEST, http=_http([(200, {}, b"{}")]))
    assert r.status == MOD.EXISTS


def test_fabricated_digest_absent() -> None:
    body = b'{"errors":[{"code":"MANIFEST_UNKNOWN","message":"manifest unknown"}]}'
    r = MOD.check_manifest(IMAGE, DIGEST, http=_http([(404, {}, body)]))
    assert r.status == MOD.ABSENT


# ── unreachable is DISTINCT from absent ─────────────────────────────────────────────────────

def test_transport_failure_is_unreachable_not_absent() -> None:
    r = MOD.check_manifest(IMAGE, DIGEST, http=_http([TimeoutError("timed out")]))
    assert r.status == MOD.UNREACHABLE, "a timeout must never be reported as a fabricated digest"


def test_5xx_is_unreachable() -> None:
    r = MOD.check_manifest(IMAGE, DIGEST, http=_http([(503, {}, b"bad gateway")]))
    assert r.status == MOD.UNREACHABLE


# ── the private-repo Bearer token exchange ─────────────────────────────────────────────────

def test_auth_challenge_then_token_then_exists() -> None:
    challenge = {"www-authenticate":
                 'Bearer realm="https://ghcr.io/token",service="ghcr.io",'
                 'scope="repository:socioprophet/prophet-platform/search-orchestrator:pull"'}
    seq = [
        (401, challenge, b""),                       # first HEAD -> challenge
        (200, {}, json.dumps({"token": "T"}).encode()),  # token endpoint GET
        (200, {}, b"{}"),                            # retried HEAD with the token -> exists
    ]
    r = MOD.check_manifest(IMAGE, DIGEST, username="x-access-token", password="p",
                           http=_http(seq))
    assert r.status == MOD.EXISTS


def test_auth_challenge_then_token_then_absent() -> None:
    challenge = {"www-authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io"'}
    body = b'{"errors":[{"code":"MANIFEST_UNKNOWN"}]}'
    seq = [
        (401, challenge, b""),
        (200, {}, json.dumps({"token": "T"}).encode()),
        (404, {}, body),                             # authenticated, and the digest is unknown
    ]
    r = MOD.check_manifest(IMAGE, DIGEST, username="x-access-token", password="p",
                           http=_http(seq))
    assert r.status == MOD.ABSENT, "authenticated 404 is the real fabricated-digest verdict"


def test_unsatisfiable_auth_is_unreachable_never_pass() -> None:
    # 401, and the token endpoint refuses our creds -> we cannot prove existence -> UNREACHABLE.
    challenge = {"www-authenticate": 'Bearer realm="https://ghcr.io/token",service="ghcr.io"'}
    seq = [
        (401, challenge, b""),
        (401, {}, b"denied"),   # token endpoint denies -> no bearer minted
    ]
    r = MOD.check_manifest(IMAGE, DIGEST, http=_http(seq))
    assert r.status == MOD.UNREACHABLE


# ── the manifest/lock roll-ups return the fail-closed exit codes ────────────────────────────

def test_verify_all_absent_returns_exit_absent() -> None:
    body = b'{"errors":[{"code":"MANIFEST_UNKNOWN"}]}'
    rc = MOD._verify_all([(IMAGE, DIGEST)], http=_http([(404, {}, body)]))
    assert rc == MOD.EXIT_ABSENT


def test_verify_all_unreachable_returns_exit_unreachable() -> None:
    rc = MOD._verify_all([(IMAGE, DIGEST)], http=_http([ConnectionError("no route")]))
    assert rc == MOD.EXIT_UNREACHABLE


def test_verify_all_exists_returns_ok() -> None:
    rc = MOD._verify_all([(IMAGE, DIGEST)], http=_http([(200, {}, b"{}")]))
    assert rc == MOD.EXIT_OK


def test_parse_ref_rejects_non_digest() -> None:
    for bad in ("ghcr.io/x/y:latest", "ghcr.io/x/y", "ghcr.io/x/y@sha256:short"):
        try:
            MOD.parse_ref(bad)
        except SystemExit:
            pass
        else:
            raise AssertionError(f"parse_ref must reject {bad!r}")


def test_manifest_rollup_reads_components(tmp_path) -> None:
    m = tmp_path / "rt.manifest.json"
    m.write_text(json.dumps({"components": [{"image": IMAGE, "digest": DIGEST}]}), encoding="utf-8")
    rc = MOD._verify_all(MOD._components_from_manifest(m), http=_http([(200, {}, b"{}")]))
    assert rc == MOD.EXIT_OK


# ── GAR (GCP Artifact Registry) — the estate's real GKE registry ────────────────────────────

GAR_IMAGE = "us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/search-orchestrator"


def _recording_http(responses):
    """Like _http, but records the request (method, url, headers) of every call so a test can
    assert HOW the registry was queried (e.g. that a GAR Bearer was presented)."""
    calls = iter(responses)
    seen: list[tuple] = []

    def fn(method, url, headers):
        seen.append((method, url, dict(headers)))
        item = next(calls)
        if isinstance(item, Exception):
            raise item
        return item

    fn.seen = seen  # type: ignore[attr-defined]
    return fn


def test_gar_host_is_detected() -> None:
    assert MOD._is_gar("us-central1-docker.pkg.dev")
    assert MOD._is_gar("europe-west1-docker.pkg.dev")
    assert not MOD._is_gar("ghcr.io")
    assert not MOD._is_gar("registry.socioprophet.ai")


def test_gar_env_token_presented_as_bearer_and_exists(monkeypatch) -> None:
    monkeypatch.setenv("GAR_ACCESS_TOKEN", "ya29.FAKE-WIF-TOKEN")
    http = _recording_http([(200, {}, b"{}")])
    r = MOD.check_manifest(GAR_IMAGE, DIGEST, http=http)
    assert r.status == MOD.EXISTS
    # The GAR access token must have gone out as a raw Bearer on the FIRST request — no
    # anonymous 401 round-trip needed for a private GAR digest.
    _, url, headers = http.seen[0]  # type: ignore[attr-defined]
    assert url.startswith("https://us-central1-docker.pkg.dev/v2/")
    assert headers.get("Authorization") == "Bearer ya29.FAKE-WIF-TOKEN"


def test_gar_fabricated_digest_absent(monkeypatch) -> None:
    monkeypatch.setenv("GAR_ACCESS_TOKEN", "ya29.FAKE-WIF-TOKEN")
    body = b'{"errors":[{"code":"MANIFEST_UNKNOWN","message":"manifest unknown"}]}'
    r = MOD.check_manifest(GAR_IMAGE, DIGEST, http=_http([(404, {}, body)]))
    assert r.status == MOD.ABSENT, "an authenticated GAR 404 is the fabricated-digest verdict"


def test_gar_unreachable_is_distinct_from_absent(monkeypatch) -> None:
    monkeypatch.setenv("GAR_ACCESS_TOKEN", "ya29.FAKE-WIF-TOKEN")
    r = MOD.check_manifest(GAR_IMAGE, DIGEST, http=_http([(503, {}, b"upstream error")]))
    assert r.status == MOD.UNREACHABLE


def test_gar_no_token_then_challenge_exchange_with_oauth2accesstoken(monkeypatch) -> None:
    # No direct-bearer env token, but the token realm accepts the resolved GAR identity via the
    # standard WWW-Authenticate exchange. The exchange must present username `oauth2accesstoken`.
    monkeypatch.delenv("GAR_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDSDK_AUTH_ACCESS_TOKEN", raising=False)
    challenge = {"www-authenticate":
                 'Bearer realm="https://us-central1-docker.pkg.dev/v2/token",'
                 'service="us-central1-docker.pkg.dev"'}
    http = _recording_http([
        (401, challenge, b""),                                # anonymous HEAD -> challenge
        (200, {}, json.dumps({"token": "GARTOK"}).encode()),  # token endpoint
        (200, {}, b"{}"),                                     # retried HEAD -> exists
    ])
    r = MOD.check_manifest(GAR_IMAGE, DIGEST, username=MOD._GAR_USERNAME, password="ya29.X",
                           http=http)
    assert r.status == MOD.EXISTS
    # the Basic auth to the token realm must carry oauth2accesstoken:...
    import base64
    _, _, tok_headers = http.seen[1]  # type: ignore[attr-defined]
    assert base64.b64encode(b"oauth2accesstoken:ya29.X").decode() in tok_headers.get("Authorization", "")
