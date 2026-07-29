"""owl-reasoner — RDFS/OWL entailment + SHACL, over KKO-typed Turtle."""
from fastapi.testclient import TestClient
from owl_reasoner.server import app
from owl_reasoner.reasoner import reason

client = TestClient(app)

KKO_TTL = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix kko: <http://kbpedia.org/ontologies/kko#> .
@prefix ex: <http://ex/> .
ex:acme a kko:Particulars . kko:Particulars rdfs:subClassOf kko:Entity ."""


def test_healthz():
    assert client.get("/healthz").json()["ok"] is True


def test_rdfs_entailment_derives_superclass_membership():
    # ex:acme a kko:Particulars + Particulars ⊑ Entity  ⊢  ex:acme a kko:Entity  (a DERIVATION, not stated)
    out = reason(KKO_TTL, inference="rdfs")
    assert out["entailed_triples"] >= 1
    assert any("acme" in e and "Entity" in e for e in out["entailments"])


def test_inference_none_derives_nothing():
    assert reason(KKO_TTL, inference="none")["entailed_triples"] == 0


def test_reason_endpoint():
    r = client.post("/reason", json={"turtle": KKO_TTL, "inference": "rdfs"})
    assert r.status_code == 200 and r.json()["entailed_triples"] >= 1


def test_shacl_validation_report():
    shapes = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix kko: <http://kbpedia.org/ontologies/kko#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
[] a sh:NodeShape ; sh:targetClass kko:Particulars ; sh:property [ sh:path rdfs:label ; sh:minCount 0 ] ."""
    out = reason(KKO_TTL, shapes=shapes, inference="rdfs")
    assert "shacl" in out and out["shacl"]["conforms"] is True


def test_reason_project_degrades_when_studio_unreachable():
    r = client.post("/reason/project", params={"project": "team-x"})
    assert r.status_code == 200
    assert r.json()["entailed_triples"] == 0  # graph pull fails in test → honest empty


def test_tbox_graph_extracts_classes_and_edges():
    from owl_reasoner.ontology_graph import tbox_graph
    ttl = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix ex: <http://ex/> .
ex:Animal a owl:Class ; rdfs:label "Animal" .
ex:Dog a owl:Class ; rdfs:subClassOf ex:Animal .
ex:owns a owl:ObjectProperty ; rdfs:domain ex:Person ; rdfs:range ex:Dog ; rdfs:label "owns" ."""
    g = tbox_graph(ttl)
    ids = {n["id"] for n in g["nodes"]}
    assert "http://ex/Animal" in ids and "http://ex/Dog" in ids
    # subClassOf edge Dog→Animal
    assert any(e["type"] == "subClassOf" and e["source"].endswith("Dog") and e["target"].endswith("Animal") for e in g["edges"])
    # object-property edge Person→Dog labeled "owns"
    assert any(e["type"] == "objectProperty" and e["label"] == "owns" for e in g["edges"])


def test_ontology_graph_endpoint():
    ttl = "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n<http://ex/A> a owl:Class ."
    r = client.post("/ontology/graph", json={"turtle": ttl})
    assert r.status_code == 200 and r.json()["counts"]["classes"] == 1


DOC_TTL = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix ex: <http://ex/> .
ex: a owl:Ontology ; dct:title "Example Ontology" ; owl:versionInfo "1.0" ; rdfs:comment "A tiny ontology." .
ex:Animal a owl:Class ; rdfs:label "Animal" ; rdfs:comment "A living creature." .
ex:Dog a owl:Class ; rdfs:label "Dog" ; rdfs:subClassOf ex:Animal .
ex:owns a owl:ObjectProperty ; rdfs:label "owns" ; rdfs:domain ex:Person ; rdfs:range ex:Dog ."""


def test_extract_ontology_model():
    from owl_reasoner.ontology_doc import extract_ontology
    m = extract_ontology(DOC_TTL)
    assert m["header"]["title"] == "Example Ontology" and m["header"]["version"] == "1.0"
    dog = next(c for c in m["classes"] if c["label"] == "Dog")
    assert dog["superClasses"] == ["http://ex/Animal"]
    owns = next(p for p in m["properties"] if p["label"] == "owns")
    assert owns["kind"] == "object" and owns["range"] == ["http://ex/Dog"]


def test_ontology_doc_endpoint_html_and_json():
    r = client.post("/ontology/doc", json={"turtle": DOC_TTL})
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    body = r.text
    assert "Example Ontology" in body and "Animal" in body and "owns" in body
    assert "<h1>" in body and 'class="badge"' in body      # rendered doc page
    j = client.post("/ontology/doc", json={"turtle": DOC_TTL, "format": "json"})
    assert j.status_code == 200 and j.json()["counts"]["classes"] == 2


def _leaves(node):
    """All asserted-leaf conclusions under a proof node."""
    if node.get("asserted"):
        return [node["conclusion"]]
    out = []
    for pr in node.get("premises", []):
        out += _leaves(pr)
    return out


def test_justification_traces_type_propagation():
    # ex:acme a kko:Particulars + Particulars ⊑ Entity ⊢ ex:acme a Entity — with a WHY trace
    out = reason(KKO_TTL, inference="rdfs", explain=True)
    js = out["justifications"]
    tp = next(j for j in js if "acme" in j["conclusion"] and "Entity" in j["conclusion"])
    assert tp["rule"].startswith("rdfs9")
    # every leaf premise is an ASSERTED fact grounding the conclusion
    leaves = _leaves(tp)
    assert any("acme" in p and "Particulars" in p for p in leaves)
    assert any("Particulars" in p and "Entity" in p for p in leaves)
    assert "justification_coverage" in out and out["justification_coverage"]["explained"] >= 1


def test_justification_is_SOUND_never_cites_underived_premise():
    # A⊑B⊑C⊑D ⊢ A⊑D. The OLD 1-ply code cited the UNDERIVED 'B subClassOf D' as a premise (bug).
    # A sound proof must ground ONLY in the three asserted subClassOf facts.
    ttl = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://ex/> .
ex:A rdfs:subClassOf ex:B . ex:B rdfs:subClassOf ex:C . ex:C rdfs:subClassOf ex:D ."""
    out = reason(ttl, inference="rdfs", explain=True)
    j = next(j for j in out["justifications"] if j["conclusion"] == "A subClassOf D")
    asserted = {"A subClassOf B", "B subClassOf C", "C subClassOf D"}
    leaves = set(_leaves(j))
    assert leaves <= asserted, f"proof leaves must be asserted facts only, got {leaves - asserted}"
    assert leaves == asserted, "the full derivation must bottom out in all three stated facts"


def test_owl2rl_profile_alias_and_label():
    out = reason(KKO_TTL, inference="owl2rl")
    assert out["inference"] == "owlrl"           # alias normalized
    assert out["profile"] == "OWL 2 RL"          # human-readable profile label


def test_subclass_transitivity_justification():
    ttl = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <http://ex/> .
ex:A rdfs:subClassOf ex:B . ex:B rdfs:subClassOf ex:C ."""
    out = reason(ttl, inference="rdfs", explain=True)
    j = next(j for j in out["justifications"] if j["conclusion"] == "A subClassOf C")
    assert j["rule"].startswith("rdfs11")
    assert set(_leaves(j)) == {"A subClassOf B", "B subClassOf C"}


def test_reason_endpoint_explain():
    r = client.post("/reason", json={"turtle": KKO_TTL, "inference": "rdfs", "explain": True})
    assert r.status_code == 200
    assert isinstance(r.json()["justifications"], list) and len(r.json()["justifications"]) >= 1


# ─── KKO TBox auto-load (with_kko) — entail over the real ontology, no inline axioms ─────────────
KKO_LEAF_TTL = """@prefix kko: <http://kbpedia.org/ontologies/kko#> .
@prefix ex: <http://ex/> .
ex:x a kko:Suchness ."""   # asserts ONLY the leaf type — the subClassOf chain lives in the vendored TBox


def test_with_kko_entails_ancestor_type_without_inline_axioms():
    # Suchness ⊑ FirstMonads ⊑ Monads is in the KKO TBox, not the input, so these are DERIVATIONS.
    out = reason(KKO_LEAF_TTL, inference="rdfs", with_kko=True, limit=20000)
    assert out["kko_tbox"]["loaded"] is True
    assert out["kko_tbox"]["triples"] > 3000            # the full KKO n3 (~3978 triples)
    assert "x type Monads" in out["entailments"]        # ex:x a kko:Monads, via the KKO subClassOf chain
    assert "x type FirstMonads" in out["entailments"]   # the intermediate ancestor too


def test_without_kko_no_ancestor_entailment():
    out = reason(KKO_LEAF_TTL, inference="rdfs")         # TBox NOT loaded
    # Asserted by property rather than exact dict equality: the status gained a `requested`
    # field so a request can no longer be reported as an outcome, and a frozen literal here
    # would fail on any future addition without saying anything about behaviour.
    assert out["kko_tbox"]["requested"] is False
    assert out["kko_tbox"]["loaded"] is False
    assert out["kko_tbox"]["triples"] == 0
    # not requested is not a failure, so no reason is attached
    assert "unavailable_reason" not in out["kko_tbox"]
    assert not any("Monads" in e for e in out["entailments"])  # can't derive an ancestor with no axioms


def test_with_kko_endpoint():
    r = client.post("/reason", json={"turtle": KKO_LEAF_TTL, "inference": "rdfs", "with_kko": True})
    assert r.status_code == 200
    j = r.json()
    assert j["kko_tbox"]["loaded"] is True and j["kko_tbox"]["triples"] > 3000
    assert j["entailed_triples"] > 1000                 # RDFS closure over data + the KKO TBox


def test_tabular_rdf_maps_rows_with_class_and_predicates():
    from owl_reasoner.tabular_rdf import map_rows
    rows = [
        {"id": "1", "full_name": "Jane Doe", "employer": "acme"},
        {"id": "2", "full_name": "John Roe", "employer": "acme"},
        {"full_name": "No Id"},   # lacks subject key → skipped
    ]
    mapping = {
        "base": "http://ex/",
        "subject_template": "person/{id}",
        "class": "Person",
        "predicates": {"full_name": "foaf:name", "employer": "http://ex/employer"},
        "object_iri": {"employer": "org/{employer}"},
        "prefixes": {"foaf": "http://xmlns.com/foaf/0.1/"},
    }
    out = map_rows(rows, mapping)
    assert out["mapped"] == 2 and out["skipped"] == 1
    ttl = out["turtle"]
    assert "person/1" in ttl and "Jane Doe" in ttl
    assert "org/acme" in ttl                       # employer mapped as an IRI reference, not a literal
    assert "foaf:name" in ttl or "name" in ttl     # CURIE-bound predicate


def test_virtualize_endpoint_json_and_turtle():
    body = {
        "rows": [{"id": "1", "full_name": "Jane"}],
        "mapping": {"base": "http://ex/", "subject_template": "p/{id}", "class": "Person",
                    "predicates": {"full_name": "http://ex/name"}},
    }
    r = client.post("/virtualize", json=body)
    assert r.status_code == 200 and r.json()["mapped"] == 1 and r.json()["triples"] >= 2
    t = client.post("/virtualize", json={**body, "format": "turtle"})
    assert t.status_code == 200 and "text/turtle" in t.headers["content-type"] and "Jane" in t.text


def test_virtualize_400_without_subject_template():
    r = client.post("/virtualize", json={"rows": [{"id": "1"}], "mapping": {"base": "http://ex/"}})
    assert r.status_code == 400


# `kko_tbox.loaded` used to be the caller's REQUEST flag. _kko_tbox() degrades to an empty
# graph when the vendored .n3 is missing or unparseable — correct, so a bad file cannot take
# reasoning down — but with `loaded: with_kko` the response then claimed the ontology was in
# play while `with_kko` was silently a no-op. pyproject declared no package-data, so that was
# the state of every installed wheel while a source checkout passed.


def test_kko_status_separates_requested_from_loaded():
    from owl_reasoner.reasoner import kko_tbox_status

    assert kko_tbox_status(False, 0) == {"requested": False, "loaded": False, "triples": 0}
    assert kko_tbox_status(True, 335) == {"requested": True, "loaded": True, "triples": 335}


def test_kko_status_refuses_to_claim_loaded_with_no_triples():
    from owl_reasoner.reasoner import kko_tbox_status

    s = kko_tbox_status(True, 0)
    assert s["requested"] is True
    assert s["loaded"] is False, "a request must never be reported as an outcome"
    assert "unavailable_reason" in s, "the response must say why, not leave a client to infer it from a zero"


def test_kko_reports_not_loaded_when_the_tbox_file_is_absent(monkeypatch):
    """The wheel scenario, exercised rather than assumed.

    Point _KKO_PATH at a file that does not exist, clear the lru_cache, and confirm the
    reasoner reports loaded=False instead of echoing the request.
    """
    from owl_reasoner import reasoner as R
    from pathlib import Path

    R._kko_tbox.cache_clear()
    monkeypatch.setattr(R, "_KKO_PATH", Path("/nonexistent/kko-missing.n3"))
    try:
        out = R.reason("<urn:a> a <urn:B> .", with_kko=True)
        assert out["kko_tbox"]["requested"] is True
        assert out["kko_tbox"]["loaded"] is False
        assert out["kko_tbox"]["triples"] == 0
        assert "unavailable_reason" in out["kko_tbox"]
    finally:
        R._kko_tbox.cache_clear()


def test_kko_actually_loads_from_the_repo_checkout():
    from owl_reasoner import reasoner as R

    R._kko_tbox.cache_clear()
    out = R.reason("<urn:a> a <urn:B> .", with_kko=True)
    assert out["kko_tbox"]["loaded"] is True
    assert out["kko_tbox"]["triples"] > 0, "the vendored TBox must actually parse"
    assert "unavailable_reason" not in out["kko_tbox"]


def test_kko_tbox_is_declared_as_package_data():
    """Without this the .n3 is absent from a built wheel and with_kko is a no-op in every
    installed deployment — the condition that made the reporting bug invisible."""
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cfg = tomllib.loads((root / "pyproject.toml").read_text())
    patterns = cfg["tool"]["setuptools"]["package-data"]["owl_reasoner"]
    assert any(p.endswith(".n3") for p in patterns), f"the TBox must ship in the wheel; got {patterns}"
