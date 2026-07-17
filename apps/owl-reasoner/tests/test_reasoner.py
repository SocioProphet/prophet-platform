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
