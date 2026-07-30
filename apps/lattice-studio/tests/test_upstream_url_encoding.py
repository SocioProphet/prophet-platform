"""The project name reaches hellgraph as a VALUE, never as query syntax.

Copilot #964 (server.py:3052), unanswered: `coll` is derived from the caller-controlled
`project` and interpolated straight into the upstream query string. proj_collection()
strips dashes and truncates to 12 characters but does not restrict the character set, so
`&`, `=` and `#` survive into the URL:

    project="&limit=99999"
      -> coll="proj-&limit=99999"
      -> GET /api/graph/subgraph?label=proj-&limit=99999&limit=500

which hands the caller control of an upstream parameter the endpoint never meant to
expose. Percent-encoding at the boundary fixes it without touching proj_collection() —
that mapping mirrors Noetica's projectCollectionId, and changing it would silently query
a different collection than Noetica writes to.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

import lattice_studio.server as srv


CAPTURED: list[str] = []


@pytest.fixture(autouse=True)
def capture_upstream(monkeypatch):
    """Record every upstream URL and answer nothing, so only URL construction is under test."""
    CAPTURED.clear()

    async def fake_req(client, method, url, json=None):
        CAPTURED.append(url)
        return None, "stubbed"

    monkeypatch.setattr(srv, "_req", fake_req)
    yield


def _subgraph_urls() -> list[str]:
    return [u for u in CAPTURED if "/api/graph/subgraph" in u]


@pytest.mark.parametrize("project", [
    "&limit=99999",
    "x&debug=1",
    "#frag",
    "a=b&c=d",
    "?x=1",
])
def test_a_hostile_project_name_cannot_inject_an_upstream_parameter(project):
    from fastapi.testclient import TestClient

    client = TestClient(srv.app)
    client.get("/api/studio/documents", params={"project": project})

    urls = _subgraph_urls()
    assert urls, "expected the documents view to call /api/graph/subgraph"
    for url in urls:
        q = parse_qs(urlparse(url).query, keep_blank_values=True)
        # The caller's text must appear as the VALUE of label and nowhere else.
        assert set(q) <= {"label", "limit"}, f"injected parameter(s) {set(q) - {'label', 'limit'}} in {url}"
        assert q.get("limit") == ["500"], f"limit was overridden: {q.get('limit')} in {url}"
        assert len(q.get("label", [])) == 1, f"label split into multiple values in {url}"
        assert urlparse(url).fragment == "", f"a fragment truncated the query: {url}"


def test_the_ordinary_project_name_is_unchanged_on_the_wire():
    """Encoding must not alter the collection actually queried — proj_collection() mirrors
    Noetica's projectCollectionId, and a changed value would query the wrong collection."""
    from fastapi.testclient import TestClient

    client = TestClient(srv.app)
    client.get("/api/studio/documents", params={"project": "default"})

    urls = _subgraph_urls()
    assert urls
    q = parse_qs(urlparse(urls[0]).query)
    assert q["label"] == [srv.proj_collection("default")] == ["proj-default"]
