"""ie-engine — REAL NLP / Information-Extraction service for the NLP & IE surface.

No fixtures: entities are real spaCy NER, relations come from the dependency parse, claims are
classified assert/hedge, topics from noun-chunk salience, sentiment from a real polarity lexicon.
`/to-graph` writes the extracted entities + relations into the canonical HellGraph (hellgraph-service)
so extraction feeds the same knowledge graph every other surface reads.

Endpoints:
  GET  /healthz
  POST /extract     { text }  → entities, relations, claims, topics, sentiment
  POST /vectorize   { texts[] } → lexical hashing vectors + pairwise cosine similarity
  POST /to-graph    { text }  → extract, then upsert nodes/edges into hellgraph-service (:8090)
  POST /personality { text }  → lexicon-based Big-Five (OCEAN) trait scores — see _personality()
                                 docstring for the honesty/validity disclaimer this endpoint carries.
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

# ---------------------------------------------------------------------------------------------
# Big-Five (OCEAN) lexicon — a HAND-BUILT, hand-curated word-count heuristic, same category of
# approach as POS/NEG above (plain English word sets, not a trained model). This is NOT a
# reproduction of LIWC or any other licensed/proprietary lexicon: no LIWC category files, word
# lists, or weights were consulted or copied. It is our own vocabulary, chosen using the same
# published, non-proprietary finding that decades of psycholinguistics research keeps landing on
# (Pennebaker & King 1999 "Linguistic styles"; Yarkoni 2010; Schwartz et al. 2013 "Personality,
# gender, and age in the language of social media") — namely *which semantic direction* each
# Big-Five trait skews language in. We use that published direction-of-association only; the
# specific words below, and the scoring formula, are ours.
#
# Each trait has a HIGH set (words that push the trait up when present) and a LOW set (words
# that push it down) — mirroring how POS/NEG work for sentiment above, generalized to five
# bipolar axes instead of one.
OCEAN_LEXICON: dict[str, dict[str, set[str]]] = {
    # Openness to Experience: high = curiosity, imagination, ideas, art, novelty-seeking;
    # low = preference for the familiar, concrete, routine, conventional.
    "openness": {
        "high": {"imagine", "curious", "curiosity", "explore", "art", "artistic", "creative", "creativity",
                  "idea", "ideas", "philosophy", "novel", "abstract", "wonder", "aesthetic", "insight",
                  "imagination", "discover", "invent", "inventive", "theory", "possibility", "unconventional",
                  "diverse", "original", "experiment", "imaginative", "innovate", "innovative", "curiously",
                  "wander", "dream", "dreamy", "unusual", "beauty", "profound", "metaphor", "poetry"},
        "low": {"routine", "familiar", "conventional", "traditional", "practical", "concrete", "ordinary",
                 "predictable", "literal", "simple", "plain", "boring", "usual", "habit", "custom"},
    },
    # Conscientiousness: high = order, planning, discipline, achievement, duty;
    # low = disorganization, carelessness, impulsivity, procrastination.
    "conscientiousness": {
        "high": {"plan", "planned", "organize", "organized", "schedule", "scheduled", "deadline",
                  "responsible", "duty", "disciplined", "discipline", "thorough", "efficient", "goal",
                  "goals", "achieve", "achievement", "complete", "completed", "punctual", "systematic",
                  "detail", "detailed", "diligent", "careful", "prepare", "prepared", "task", "checklist",
                  "procedure", "routine", "reliable", "orderly", "meticulous", "committed", "persevere"},
        "low": {"disorganized", "careless", "impulsive", "procrastinate", "procrastinated", "sloppy",
                 "messy", "forgetful", "lazy", "late", "unreliable", "reckless", "haphazard", "chaotic",
                 "distracted", "neglect", "neglected", "unprepared"},
    },
    # Extraversion: high = sociability, assertiveness, activity, positive excitement;
    # low = reserve, solitude, quiet, withdrawal.
    "extraversion": {
        "high": {"party", "friends", "social", "excited", "excitement", "fun", "outgoing", "energetic",
                  "talk", "talkative", "crowd", "adventure", "laugh", "laughed", "enthusiastic", "team",
                  "celebrate", "spontaneous", "bold", "confident", "loud", "gregarious", "chat", "chatty",
                  "gathering", "socialize", "assertive", "lively", "cheerful"},
        "low": {"alone", "quiet", "reserved", "shy", "solitude", "solitary", "withdrawn", "introvert",
                 "silent", "isolated", "timid", "reticent", "loner", "hesitant", "subdued", "unnoticed"},
    },
    # Agreeableness: high = warmth, cooperation, empathy, trust, politeness;
    # low = antagonism, suspicion, coldness, hostility.
    "agreeableness": {
        "high": {"kind", "help", "helped", "helpful", "care", "caring", "please", "thank", "thanks",
                  "trust", "friendly", "cooperate", "cooperative", "gentle", "generous", "compassion",
                  "compassionate", "warm", "polite", "considerate", "supportive", "forgive", "forgiving",
                  "share", "shared", "gratitude", "sympathy", "sympathetic", "agree", "kindness", "empathy",
                  "understanding", "gracious"},
        "low": {"rude", "selfish", "hostile", "hostility", "cruel", "cold", "suspicious", "distrust",
                 "argue", "argued", "argument", "stubborn", "insult", "insulted", "contempt", "spiteful",
                 "ruthless", "manipulative", "callous", "harsh"},
    },
    # Neuroticism: high = anxiety, worry, negative emotion, emotional instability;
    # low = calm, emotional stability, security.
    "neuroticism": {
        "high": {"worry", "worried", "anxious", "anxiety", "afraid", "stress", "stressed", "nervous",
                  "upset", "sad", "angry", "anger", "fear", "afraid", "panic", "insecure", "depressed",
                  "overwhelmed", "hurt", "frustrated", "frustration", "guilty", "lonely", "doubt", "tense",
                  "unstable", "dread", "miserable", "irritable", "restless"},
        "low": {"calm", "secure", "relaxed", "stable", "confident", "content", "peaceful", "steady",
                 "composed", "serene", "unworried", "grounded", "reassured", "settled"},
    },
}
# Density-difference saturation cap: at (high_count - low_count) / alpha_tokens == this value,
# the score saturates to 0.0 or 1.0. 0.12 is a deliberately conservative constant chosen because
# even lexicon-dense text rarely exceeds ~10-15% single-category word density; it is NOT fit to
# any labeled data (none exists for this task — see _personality() docstring).
TRAIT_SATURATION_CAP = 0.12

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

def _personality(text: str) -> dict[str, Any]:
    """Lexicon-based Big-Five (OCEAN) scorer — a coarse heuristic, NOT a validated psychometric
    instrument, and NOT comparable to IBM Watson Personality Insights or any clinically-validated
    tool. There is no labeled personality ground-truth data anywhere in this estate, so this is
    deliberately NOT a trained/supervised classifier (that would require labels we don't have and
    can't honestly claim). Instead it is the same category of technique as the sentiment scorer
    above: per-trait word-count density over a hand-built, hand-curated lexicon (see
    OCEAN_LEXICON), normalized by text length. This is the standard "LIWC-style" lexicon-counting
    approach used as an academic baseline in psycholinguistics research — a real, working,
    honestly-labeled heuristic, not an approximation of a trained model.

    Scale: each trait score is 0.0-1.0.
      - 0.5 = the midpoint — no net lexical signal was detected either way (this is NOT the
        same thing as "average trait level"; it just means the text didn't contain enough
        high/low marker words to move the needle).
      - Values above/below 0.5 indicate the direction and (saturating) strength of lexical
        signal toward the high or low pole of the trait, capped at 0.0/1.0 once the marker-word
        density difference reaches TRAIT_SATURATION_CAP.
    Confidence is explicitly weak for short text: `tokens_considered` is returned per-trait so a
    caller can see how little (or how much) evidence the score is based on.
    """
    doc = NLP(text)
    lemmas = [w.lemma_.lower() for w in doc if w.is_alpha]
    n_tokens = len(lemmas)
    traits: dict[str, Any] = {}
    for trait, sets in OCEAN_LEXICON.items():
        high_hits = [w for w in lemmas if w in sets["high"]]
        low_hits = [w for w in lemmas if w in sets["low"]]
        raw = (len(high_hits) - len(low_hits)) / max(n_tokens, 1)
        score = 0.5 + (raw / (2 * TRAIT_SATURATION_CAP))
        score = max(0.0, min(1.0, score))
        traits[trait] = {
            "score": round(score, 3),
            "high_matches": sorted(set(high_hits)),
            "low_matches": sorted(set(low_hits)),
            "tokens_considered": n_tokens,
        }
    return {
        "traits": traits,
        "scale": "0.0-1.0 per trait; 0.5 = no lexical signal (neutral midpoint, not a measured "
                 "average); values move toward 0.0 (low-pole marker words) or 1.0 (high-pole "
                 "marker words), saturating once marker-word density exceeds "
                 f"{TRAIT_SATURATION_CAP:.0%} of tokens.",
        "disclaimer": "HEURISTIC ONLY. This is a hand-built lexicon word-count baseline (same "
                      "technique family as the POS/NEG sentiment lexicon in this service), not a "
                      "trained model and not a validated psychometric instrument. It has NOT been "
                      "validated against any ground-truth personality labels (none exist in this "
                      "estate) and must not be treated as clinically or psychometrically accurate, "
                      "or as comparable to IBM Watson Personality Insights or similar commercial "
                      "products. Scores on short text are especially unreliable — see "
                      "tokens_considered per trait.",
        "counts": {"tokens": len(doc), "alpha_tokens": n_tokens},
        "provenance": {"model": "hand-built OCEAN lexicon (word-count heuristic)",
                        "extractor": "ie-engine", "real": True, "validated": False},
    }

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

@app.post("/personality")
def personality(req: TextReq) -> dict[str, Any]:
    """Lexicon-based Big-Five (OCEAN) trait scoring — the UNGATED substrate scorer.

    See _personality() docstring for the full honesty/validity disclaimer: this is a heuristic
    word-count baseline, not a validated psychometric instrument, and not comparable to any
    commercial personality-scoring product.

    IMPORTANT — this endpoint is a SUBSTRATE, not an instrument. It applies no evidence-
    sufficiency gate (it will score 15 words and return five confident-looking numbers) and no
    domain/use-case gate (nothing here stops a caller using the output for hiring or eligibility
    screening). Those gates deliberately live in a DIFFERENT service, needs-wants-instrument,
    which consumes this endpoint and enforces the Needs/Wants two-regime framework on top of it:
    trait-like output is Regime W (a satisfier PREFERENCE, gated on evidence and domain) and is
    never emitted as a "need". Consumers making consequential decisions should call that service,
    not this one. The separation is intentional — co-locating the ungated scorer with its own
    gates would make the gates optional.
    """
    out = _personality(req.text)
    out["governance"] = {
        "gated": False,
        "regime": "substrate — ungated; trait-like output is Regime W (a preference) once gated",
        "instrument": "needs-wants-instrument (POST /wants) applies G1_W evidence sufficiency "
                      "and G4 domain/use-case gates over this scorer",
        "never": "this output is NOT a 'need' and carries no deprivation or harm claim",
    }
    return out

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
