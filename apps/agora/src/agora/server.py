"""Agora — the sovereign work + knowledge plane (Jira/Confluence killer) for the SocioProphet estate.

Sits alongside zot (sovereign registry) and gitea-sovereign (source control). Where those two are the
build & code substrate, Agora is the WORK & KNOWLEDGE substrate that bridges Knowledge Engineering ⇄ the
Knowledge Commons: issues / tasks / sprints (the Jira side) and wiki pages (the Confluence side) are not rows
in a side database — they are persisted as PROOF-CARRYING GRAPH FACTS over HellGraph, in the very same `proj-`
collection that Noetica and lattice-studio already share. That means every work item and page is, for free:

  • project- and team-aligned (it lives in the project's collection, which the agent team already reads),
  • citable (Studio /cite mints a sovereign DOI over it),
  • preservable + versionable (Studio /preserve seals it),
  • curatable (Studio /endorse + epistemic-weighted curation apply to it),
  • queryable live by any agent (SPARQL/Cypher/Gremlin over the kernel).

It reuses Noetica's native work model (lib/types/work.ts: WorkItem / Sprint / Project — "native = source of
truth, Jira/Linear/GitHub Issues = optional external connectors only"), moving it off localStorage and onto the
graph. Team and Page are greenfield here (neither existed in Noetica). Writes are fail-closed behind
AGORA_WRITE_TOKEN; reads follow the estate's sovereign-identity gate (socbase HS256 JWT), opt-in.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

SERVICE_VERSION = "0.1.0"
HELLGRAPH_URL = os.getenv("HELLGRAPH_URL", "http://hellgraph-service:8090")
TIMEOUT = float(os.getenv("AGORA_TIMEOUT", "5"))
# Fail-closed write gate — unset → all writes refused (reads stay open), so a public ingress can never accept an
# anonymous work/page write. Token provisioned out-of-band (Secret), same posture as lattice-studio.
AGORA_WRITE_TOKEN = os.getenv("AGORA_WRITE_TOKEN", "")
# Opt-in read gate tied to the sovereign identity plane (socbase/GoTrue HS256). Unset → reads open (compatible).
AGORA_JWT_SECRET = os.getenv("AGORA_JWT_SECRET", "")

# The Jira board columns (mirrors Noetica WorkItem.status).
WORK_STATUSES = ["backlog", "todo", "in_progress", "in_review", "done", "cancelled"]
WORK_TYPES = ["task", "epic", "story", "bug", "spike", "milestone"]

app = FastAPI(title="Agora — work + knowledge plane", version=SERVICE_VERSION)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def proj_collection(project: str) -> str:
    """Mirror Noetica projectCollectionId / lattice-studio proj_collection — proj-<12 hex, dashes stripped>,
    so Agora facts co-locate with the project's KB, extracted entities, citations and snapshots."""
    return "proj-" + re.sub(r"-", "", project)[:12]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-") or "untitled"


def require_read(authorization: str = Header(default="")) -> dict[str, Any] | None:
    """READ dependency: unset secret → open; else require a valid socbase-issued HS256 bearer token."""
    if not AGORA_JWT_SECRET:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="read requires a bearer token (AGORA_JWT_SECRET is set)")
    try:
        return jwt.decode(token, AGORA_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc


def _require_write(authorization: str) -> None:
    if not AGORA_WRITE_TOKEN:
        raise HTTPException(status_code=503, detail="agora writes disabled: AGORA_WRITE_TOKEN unset (fail-closed)")
    if authorization.removeprefix("Bearer ").strip() != AGORA_WRITE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid write token")


async def _req(client: httpx.AsyncClient, method: str, url: str, json: Any = None) -> tuple[Any, str | None]:
    """The one resilient upstream call to hellgraph-service. Returns (json_or_None, error_or_None); never raises,
    so a graph blip degrades gracefully instead of 500-ing the work board."""
    try:
        r = await client.request(method, url, json=json)
        r.raise_for_status()
        return (r.json() if r.content else {}), None
    except Exception as exc:  # noqa: BLE001 — deliberately broad; upstream health is not our contract
        return None, f"{type(exc).__name__}: {exc}"


async def _fetch_nodes(coll: str, limit: int = 1000) -> tuple[list[dict[str, Any]], str | None]:
    """Read the project's induced subgraph and return its raw nodes (each {id, labels, properties})."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        data, err = await _req(client, "GET", f"{HELLGRAPH_URL}/api/graph/subgraph?label={coll}&limit={limit}")
    if err or not data:
        return [], err
    return data.get("nodes") or [], None


def _prov(coll: str, extractor: str, actor: str | None) -> dict[str, Any]:
    """Provenance stamped on every Agora fact — same shape lattice-studio uses, so a work item / page is as
    proof-carrying as an extracted entity. epistemic_mode=attested: a work item is an ASSERTED operational fact
    (someone declared this state), which is exactly the Peircean 'attested' rung, not an observation."""
    return {"epistemic_mode": "attested", "source": actor or "agora",
            "extractor": extractor, "project": coll, "kko_type": "Particulars"}


# ── health ───────────────────────────────────────────────────────────────────────────────────────────────────
@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "agora", "version": SERVICE_VERSION}


# ── work items (the Jira side) ─────────────────────────────────────────────────────────────────────────────────
class WorkItemRequest(BaseModel):
    project: str = "default"
    title: str
    type: str = "task"                 # task | epic | story | bug | spike | milestone
    description: str | None = None
    status: str = "backlog"
    priority: str | None = None
    assignee: str | None = None        # human or agent id
    team: str | None = None
    sprint: str | None = None
    epic: str | None = None            # parent epic id (links to another WorkItem)
    tags: list[str] | None = None
    actor: str | None = None           # who authored this change (provenance)


@app.post("/api/agora/work")
async def upsert_work(req: WorkItemRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Create or update a work item, persisted as a proof-carrying HellGraph node (+ in_project / in_sprint /
    in_team / assigned_to / child_of edges). Idempotent per (project, title). Reuses Noetica's WorkItem shape."""
    _require_write(authorization)
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title required")
    if req.status not in WORK_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {WORK_STATUSES}")
    if req.type not in WORK_TYPES:
        raise HTTPException(status_code=422, detail=f"type must be one of {WORK_TYPES}")
    coll = proj_collection(req.project)
    wid = f"{coll}:work:{_slug(title)}"
    prov = _prov(coll, "agora/work-v0", req.actor)
    props = {"title": title, "type": req.type, "description": req.description or "", "status": req.status,
             "priority": req.priority or "", "assignee": req.assignee or "", "team": req.team or "",
             "sprint": req.sprint or "", "epic": req.epic or "", "tags": ",".join(req.tags or []),
             "updated_at": _now_iso(), **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": wid, "labels": [coll, "WorkItem", req.type.capitalize()], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
        edges = [("in_project", coll)]
        if req.sprint:
            edges.append(("in_sprint", f"{coll}:sprint:{_slug(req.sprint)}"))
        if req.team:
            edges.append(("in_team", f"{coll}:team:{_slug(req.team)}"))
        if req.assignee:
            edges.append(("assigned_to", f"{coll}:actor:{_slug(req.assignee)}"))
        if req.epic:
            edges.append(("child_of", f"{coll}:work:{_slug(req.epic)}"))
        for label, to in edges:
            await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                       json={"label": label, "from": wid, "to": to, "properties": prov})
    return {"work_id": wid, "title": title, "status": req.status, "project": req.project,
            "proof_carrying": True, "citable": True}


def _work_view(n: dict[str, Any]) -> dict[str, Any]:
    p = n.get("properties") or {}
    return {"work_id": n.get("id"), "title": p.get("title"), "type": p.get("type", "task"),
            "status": p.get("status", "backlog"), "priority": p.get("priority") or None,
            "assignee": p.get("assignee") or None, "team": p.get("team") or None,
            "sprint": p.get("sprint") or None, "epic": p.get("epic") or None,
            "tags": [t for t in (p.get("tags") or "").split(",") if t], "updated_at": p.get("updated_at"),
            "epistemic_mode": p.get("epistemic_mode", "attested")}


@app.get("/api/agora/board")
async def board(project: str = "default", team: str = "",
                _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The board: work items grouped into status columns (backlog → done). Optionally filtered to a team. Every
    card is a live graph fact — cite it, preserve it, query it, or hand it to the agent team, no export needed."""
    coll = proj_collection(project)
    raw, err = await _fetch_nodes(coll)
    columns: dict[str, list[dict[str, Any]]] = {s: [] for s in WORK_STATUSES}
    total = 0
    for n in raw:
        if "WorkItem" not in (n.get("labels") or []):
            continue
        v = _work_view(n)
        if team and v["team"] != team:
            continue
        columns.setdefault(v["status"], []).append(v)
        total += 1
    for s in columns:
        columns[s].sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"project": project, "team": team or None, "columns": columns, "count": total, "degraded": err}


# ── wiki pages (the Confluence side) ───────────────────────────────────────────────────────────────────────────
class PageRequest(BaseModel):
    project: str = "default"
    title: str
    body: str = ""                     # markdown
    parent: str | None = None          # parent page title (page tree)
    tags: list[str] | None = None
    actor: str | None = None


@app.post("/api/agora/page")
async def upsert_page(req: PageRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Create or update a wiki page, persisted as a proof-carrying HellGraph node (+ in_project / child_of edges
    for the page tree). Idempotent per (project, title). The Confluence side — but every page is a graph fact,
    so it's citable, preservable, and linkable to the work items and entities in the same project."""
    _require_write(authorization)
    title = req.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="title required")
    coll = proj_collection(req.project)
    pid = f"{coll}:page:{_slug(title)}"
    prov = _prov(coll, "agora/page-v0", req.actor)
    props = {"title": title, "body": req.body or "", "parent": req.parent or "",
             "tags": ",".join(req.tags or []), "updated_at": _now_iso(), **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": pid, "labels": [coll, "Page", "Wiki"], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
        await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                   json={"label": "in_project", "from": pid, "to": coll, "properties": prov})
        if req.parent:
            await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                       json={"label": "child_of", "from": pid, "to": f"{coll}:page:{_slug(req.parent)}", "properties": prov})
    return {"page_id": pid, "title": title, "project": req.project, "proof_carrying": True, "citable": True}


@app.get("/api/agora/pages")
async def pages(project: str = "default",
                _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """The wiki: project pages, newest first, each with its parent (for the page tree) and tags."""
    coll = proj_collection(project)
    raw, err = await _fetch_nodes(coll)
    out = []
    for n in raw:
        if "Page" not in (n.get("labels") or []):
            continue
        p = n.get("properties") or {}
        out.append({"page_id": n.get("id"), "title": p.get("title"), "parent": p.get("parent") or None,
                    "tags": [t for t in (p.get("tags") or "").split(",") if t], "updated_at": p.get("updated_at"),
                    "excerpt": (p.get("body") or "")[:280]})
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"project": project, "pages": out, "count": len(out), "degraded": err}


# ── teams (greenfield — align work to teams) ───────────────────────────────────────────────────────────────────
class TeamRequest(BaseModel):
    project: str = "default"
    name: str
    members: list[str] | None = None
    actor: str | None = None


@app.post("/api/agora/team")
async def upsert_team(req: TeamRequest, authorization: str = Header(default="")) -> dict[str, Any]:
    """Create or update a team, persisted as a HellGraph node with member edges. Work items align to a team via
    their in_team edge, so a board can scope to a team and the agent team reads the same graph."""
    _require_write(authorization)
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name required")
    coll = proj_collection(req.project)
    tid = f"{coll}:team:{_slug(name)}"
    prov = _prov(coll, "agora/team-v0", req.actor)
    props = {"name": name, "members": ",".join(req.members or []), "updated_at": _now_iso(), **prov}
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        _, werr = await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/node",
                             json={"id": tid, "labels": [coll, "Team"], "properties": props})
        if werr:
            raise HTTPException(status_code=502, detail=f"graph write failed: {werr}")
        await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                   json={"label": "in_project", "from": tid, "to": coll, "properties": prov})
        for m in (req.members or []):
            await _req(client, "POST", f"{HELLGRAPH_URL}/api/graph/edge",
                       json={"label": "member_of", "from": f"{coll}:actor:{_slug(m)}", "to": tid, "properties": prov})
    return {"team_id": tid, "name": name, "project": req.project, "members": req.members or [], "proof_carrying": True}


# ── the bundle (one call for the surface) ──────────────────────────────────────────────────────────────────────
@app.get("/api/agora")
async def bundle(project: str = "default",
                 _auth: dict[str, Any] | None = Depends(require_read)) -> dict[str, Any]:
    """One call for the Agora surface: the board (by status), the wiki page list, the teams, and a stats block —
    all read from the project's proj- collection, and all citable/preservable/curatable via Studio's commons."""
    coll = proj_collection(project)
    raw, err = await _fetch_nodes(coll)
    columns: dict[str, list[dict[str, Any]]] = {s: [] for s in WORK_STATUSES}
    page_list, teams = [], []
    work_n = 0
    for n in raw:
        labels = n.get("labels") or []
        p = n.get("properties") or {}
        if "WorkItem" in labels:
            v = _work_view(n)
            columns.setdefault(v["status"], []).append(v)
            work_n += 1
        elif "Page" in labels:
            page_list.append({"page_id": n.get("id"), "title": p.get("title"), "parent": p.get("parent") or None,
                              "updated_at": p.get("updated_at")})
        elif "Team" in labels:
            teams.append({"team_id": n.get("id"), "name": p.get("name"),
                          "members": [m for m in (p.get("members") or "").split(",") if m]})
    for s in columns:
        columns[s].sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    page_list.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {
        "project": project, "collection": coll,
        "board": {"columns": columns, "count": work_n},
        "pages": page_list, "teams": teams,
        "stats": {"work_items": work_n, "pages": len(page_list), "teams": len(teams)},
        # the bridge: everything here is a graph fact in the project collection, so the commons applies as-is.
        "commons": {"citable": True, "preservable": True, "curatable": True,
                    "note": "work items & pages are proof-carrying graph facts — cite/preserve/curate via Studio"},
        "degraded": err,
    }
