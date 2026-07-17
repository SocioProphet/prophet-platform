"""Agora BFF tests — work items + wiki pages + teams as proof-carrying HellGraph facts. The graph is faked by
monkeypatching srv._req, routed by URL substring (the lattice-studio test pattern)."""
from fastapi.testclient import TestClient

import agora.server as srv
from agora.server import app

client = TestClient(app)


def test_healthz():
    b = client.get("/healthz").json()
    assert b["status"] == "ok" and b["service"] == "agora"


def test_work_write_requires_token(monkeypatch):
    monkeypatch.setattr(srv, "AGORA_WRITE_TOKEN", "")
    r = client.post("/api/agora/work", json={"project": "team-x", "title": "Ship Agora"})
    assert r.status_code == 503   # fail-closed


def test_upsert_work_writes_node_and_edges(monkeypatch):
    monkeypatch.setattr(srv, "AGORA_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json)
            return ({"ok": True}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/agora/work",
                    json={"project": "team-x", "title": "Ship Agora", "type": "story", "status": "in_progress",
                          "assignee": "claude", "team": "platform", "sprint": "s1", "epic": "Estate",
                          "tags": ["estate", "graph"], "actor": "mdheller"},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert r.status_code == 200 and b["proof_carrying"] and b["citable"]
    assert b["work_id"] == "proj-teamx:work:ship-agora"
    node = next(w for w in writes if "labels" in w)
    assert node["labels"] == ["proj-teamx", "WorkItem", "Story"]
    assert node["properties"]["epistemic_mode"] == "attested"       # proof-carrying
    assert node["properties"]["source"] == "mdheller"               # actor → provenance
    edge_labels = {w["label"] for w in writes if "label" in w}
    assert {"in_project", "in_sprint", "in_team", "assigned_to", "child_of"} <= edge_labels


def test_upsert_work_rejects_bad_status(monkeypatch):
    monkeypatch.setattr(srv, "AGORA_WRITE_TOKEN", "T")
    r = client.post("/api/agora/work", json={"project": "team-x", "title": "x", "status": "wip"},
                    headers={"Authorization": "Bearer T"})
    assert r.status_code == 422


def test_board_groups_by_status_and_filters_team(monkeypatch):
    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:work:a", "labels": ["proj-teamx", "WorkItem", "Task"],
                 "properties": {"title": "A", "status": "todo", "team": "platform", "updated_at": "t2"}},
                {"id": "proj-teamx:work:b", "labels": ["proj-teamx", "WorkItem", "Bug"],
                 "properties": {"title": "B", "status": "done", "team": "platform", "updated_at": "t1"}},
                {"id": "proj-teamx:work:c", "labels": ["proj-teamx", "WorkItem", "Task"],
                 "properties": {"title": "C", "status": "todo", "team": "noetica", "updated_at": "t3"}},
                {"id": "proj-teamx:page:x", "labels": ["proj-teamx", "Page", "Wiki"], "properties": {"title": "X"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/agora/board?project=team-x&team=platform").json()
    assert b["count"] == 2                       # C (noetica) filtered out; page ignored
    assert [w["title"] for w in b["columns"]["todo"]] == ["A"]
    assert [w["title"] for w in b["columns"]["done"]] == ["B"]


def test_page_upsert_and_list(monkeypatch):
    monkeypatch.setattr(srv, "AGORA_WRITE_TOKEN", "T")
    writes = []

    async def fake_req(client, method, url, json=None):
        if "/api/graph/node" in url or "/api/graph/edge" in url:
            writes.append(json)
            return ({"ok": True}, None)
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:page:arch", "labels": ["proj-teamx", "Page", "Wiki"],
                 "properties": {"title": "Architecture", "body": "The estate has zot, gitea, agora.",
                                "parent": "", "updated_at": "t1"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    r = client.post("/api/agora/page",
                    json={"project": "team-x", "title": "Architecture", "body": "The estate has zot, gitea, agora.",
                          "parent": "Home", "tags": ["design"]},
                    headers={"Authorization": "Bearer T"})
    b = r.json()
    assert b["page_id"] == "proj-teamx:page:architecture" and b["citable"]
    node = next(w for w in writes if "labels" in w)
    assert node["labels"] == ["proj-teamx", "Page", "Wiki"]
    assert any(w.get("label") == "child_of" for w in writes)   # page-tree edge to parent

    lst = client.get("/api/agora/pages?project=team-x").json()
    assert lst["count"] == 1 and lst["pages"][0]["title"] == "Architecture"
    assert lst["pages"][0]["excerpt"].startswith("The estate")


def test_bundle_reports_board_pages_teams_and_commons_bridge(monkeypatch):
    async def fake_req(client, method, url, json=None):
        if "subgraph" in url:
            return ({"nodes": [
                {"id": "proj-teamx:work:a", "labels": ["proj-teamx", "WorkItem", "Task"],
                 "properties": {"title": "A", "status": "todo", "updated_at": "t1"}},
                {"id": "proj-teamx:page:x", "labels": ["proj-teamx", "Page", "Wiki"],
                 "properties": {"title": "X", "updated_at": "t1"}},
                {"id": "proj-teamx:team:platform", "labels": ["proj-teamx", "Team"],
                 "properties": {"name": "platform", "members": "claude,mdheller"}},
            ], "edgeList": []}, None)
        return (None, "x")
    monkeypatch.setattr(srv, "_req", fake_req)

    b = client.get("/api/agora?project=team-x").json()
    assert b["stats"] == {"work_items": 1, "pages": 1, "teams": 1}
    assert b["teams"][0]["members"] == ["claude", "mdheller"]
    assert b["commons"]["citable"] and b["commons"]["curatable"]   # the KE⇄Commons bridge
    assert b["board"]["columns"]["todo"][0]["title"] == "A"
