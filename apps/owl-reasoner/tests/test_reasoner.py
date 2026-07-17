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
