"""ie-engine — REAL NLP / Information-Extraction service for the NLP & IE surface.

No fixtures: entities are real spaCy NER, relations come from the dependency parse, claims are
classified assert/hedge, topics from noun-chunk salience, sentiment from a real polarity lexicon.
`/to-graph` writes the extracted entities + relations into the canonical HellGraph (hellgraph-service)
so extraction feeds the same knowledge graph every other surface reads.

Endpoints:
  GET  /healthz
  POST /extract   { text }  → entities, relations, claims, topics, sentiment
  POST /vectorize { texts[] } → lexical hashing vectors + pairwise cosine similarity
  POST /to-graph  { text }  → extract, then upsert nodes/edges into hellgraph-service (:8090)
"""
from __future__ import annotations
import math, os, re
from collections import Counter
from typing import Any
import httpx
import spacy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="ie-engine", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
NLP = spacy.load("en_core_web_sm")
HELLGRAPH = os.environ.get("HELLGRAPH_BASE", "http://127.0.0.1:8090")

# spaCy entity labels → our type system
TYPE_MAP = {"ORG": "Org", "PERSON": "Person", "DATE": "Date", "TIME": "Date", "MONEY": "Money",
            "GPE": "Place", "LOC": "Place", "FAC": "Place", "PRODUCT": "Product", "LAW": "Law",
            "NORP": "Group", "EVENT": "Event", "PERCENT": "Percent", "CARDINAL": "Quantity", "QUANTITY": "Quantity"}
HEDGES = {"expect", "expected", "likely", "may", "might", "could", "should", "estimate", "estimated",
          "project", "projected", "anticipate", "anticipated", "potential", "possible", "aim", "plan",
          "propose", "proposed", "reportedly", "seem", "suggest"}
POS = {"gain", "growth", "improve", "improved", "strong", "success", "benefit", "up", "rise", "align", "support", "approve"}
NEG = {"loss", "decline", "risk", "weak", "fail", "concern", "down", "fall", "penalty", "breach", "dispute", "cost", "costs"}

class TextReq(BaseModel):
    text: str

class VecReq(BaseModel):
    texts: list[str]

def _extract(text: str) -> dict[str, Any]:
    doc = NLP(text)
    seen: dict[str, dict[str, Any]] = {}
    for e in doc.ents:
        t = TYPE_MAP.get(e.label_)
        if not t:
            continue
        key = e.text.strip()
        seen.setdefault(key, {"text": key, "type": t, "spacy_label": e.label_, "mentions": 0})
        seen[key]["mentions"] += 1
    # topics: salient noun chunks (multi-word, not already an entity)
    ent_texts = {k.lower() for k in seen}
    chunks = [c.text.strip().lower() for c in doc.noun_chunks if len(c.text.split()) >= 2 and c.text.strip().lower() not in ent_texts]
    topics = [{"text": t, "type": "Topic", "count": n} for t, n in Counter(chunks).most_common(6)]
    entities = list(seen.values()) + topics

    # relations: dependency subject–verb–object triples
    relations = []
    for sent in doc.sents:
        subs = [w for w in sent if w.dep_ in ("nsubj", "nsubjpass")]
        for s in subs:
            verb = s.head
            objs = [w for w in verb.children if w.dep_ in ("dobj", "attr", "pobj", "dative")]
            objs += [w for c in verb.children if c.dep_ == "prep" for w in c.children if w.dep_ == "pobj"]
            for o in objs:
                relations.append({"from": _span(s), "relation": verb.lemma_, "to": _span(o)})
    # dedup
    rseen = set(); rel_out = []
    for r in relations:
        k = (r["from"], r["relation"], r["to"])
        if k not in rseen and r["from"] != r["to"]:
            rseen.add(k); rel_out.append(r)

    # claims: per sentence, assert vs hedge; verifiable if it carries a quantity/date/money
    claims = []
    for sent in doc.sents:
        toks = {w.lemma_.lower() for w in sent}
        hedged = bool(toks & HEDGES)
        has_fact = any(e.label_ in ("MONEY", "PERCENT", "QUANTITY", "CARDINAL", "DATE") for e in sent.ents)
        claims.append({"type": "HEDGE" if hedged else "ASSERT", "text": sent.text.strip(),
                       "verifiable": (not hedged) and has_fact})

    # sentiment: real polarity lexicon
    lemmas = [w.lemma_.lower() for w in doc if w.is_alpha]
    p = sum(1 for w in lemmas if w in POS); n = sum(1 for w in lemmas if w in NEG)
    score = round((p - n) / max(len(lemmas), 1), 3)
    label = "positive" if score > 0.02 else "negative" if score < -0.02 else "neutral"

    return {"entities": entities[:24], "relations": rel_out[:16], "claims": claims[:12],
            "topics": topics, "sentiment": {"label": label, "score": score},
            "counts": {"entities": len(seen), "relations": len(rel_out), "claims": len(claims), "tokens": len(doc)},
            "provenance": {"model": "spaCy en_core_web_sm", "extractor": "ie-engine", "real": True}}

def _span(tok) -> str:
    # widen a token to its noun-phrase span when possible
    for c in tok.doc.noun_chunks:
        if c.start <= tok.i < c.end:
            return c.text.strip()
    return tok.text

# lexical hashing vector (real, deterministic) — char 3-gram hashing → L2-normalized
def _vec(text: str, dim: int = 256) -> list[float]:
    v = [0.0] * dim
    s = re.sub(r"\s+", " ", text.lower())
    for i in range(len(s) - 2):
        v[hash(s[i:i + 3]) % dim] += 1.0
    nrm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / nrm for x in v]

def _cos(a: list[float], b: list[float]) -> float:
    return round(sum(x * y for x, y in zip(a, b)), 4)

@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "ie-engine", "model": "en_core_web_sm", "pipes": NLP.pipe_names}

@app.post("/extract")
def extract(req: TextReq) -> dict[str, Any]:
    return _extract(req.text)

@app.post("/glossary")
def glossary(req: TextReq) -> dict[str, Any]:
    """Derive a glossary: salient terms → a definition (the first sentence that introduces the term)."""
    doc = NLP(req.text)
    sents = list(doc.sents)
    terms: dict[str, dict[str, Any]] = {}
    for e in doc.ents:
        t = TYPE_MAP.get(e.label_)
        if t and t not in ("Date", "Money", "Percent", "Quantity"):
            terms.setdefault(e.text.strip(), {"term": e.text.strip(), "type": t, "count": 0})
            terms[e.text.strip()]["count"] += 1
    for c in doc.noun_chunks:
        k = c.text.strip()
        if len(k.split()) >= 2 and k not in terms:
            terms.setdefault(k, {"term": k, "type": "Concept", "count": 0})
            terms[k]["count"] += 1
    out = []
    for k, v in terms.items():
        definition = next((s.text.strip() for s in sents if k.lower() in s.text.lower()), "")
        out.append({**v, "definition": definition})
    out.sort(key=lambda x: (-x["count"], x["term"]))
    return {"terms": out[:20], "count": len(out), "provenance": {"model": "spaCy en_core_web_sm", "real": True}}

@app.post("/vectorize")
def vectorize(req: VecReq) -> dict[str, Any]:
    vecs = [_vec(t) for t in req.texts]
    sims = [[_cos(vecs[i], vecs[j]) for j in range(len(vecs))] for i in range(len(vecs))]
    return {"dim": 256, "method": "char-3gram hashing (lexical)", "vectors_preview": [v[:8] for v in vecs], "similarity": sims}

@app.post("/to-graph")
def to_graph(req: TextReq) -> dict[str, Any]:
    ex = _extract(req.text)
    slug = lambda s: "ie:" + re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48]
    posted_n = posted_e = 0
    with httpx.Client(timeout=10.0) as c:
        idx = {}
        for e in ex["entities"]:
            nid = slug(e["text"]); idx[e["text"]] = nid
            try:
                c.post(f"{HELLGRAPH}/api/graph/node", json={"id": nid, "labels": [e["type"], "Extracted"], "properties": {"name": e["text"]}})
                posted_n += 1
            except httpx.HTTPError:
                pass
        for r in ex["relations"]:
            fn, tn = idx.get(r["from"]) or slug(r["from"]), idx.get(r["to"]) or slug(r["to"])
            try:
                c.post(f"{HELLGRAPH}/api/graph/edge", json={"label": r["relation"].upper(), "from": fn, "to": tn, "properties": {"source": "ie-engine"}})
                posted_e += 1
            except httpx.HTTPError:
                pass
    return {"ok": True, "nodes_written": posted_n, "edges_written": posted_e, "graph": HELLGRAPH, **ex}
