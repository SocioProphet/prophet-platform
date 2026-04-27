import json

from lattice_studio.cli import main
from lattice_studio.ontogenesis import demo_ontogenesis_context, ontogenesis_evidence, ontogenesis_to_platform_record


def test_ontogenesis_context_binds_lattice_studio_to_semantic_governance() -> None:
    context = demo_ontogenesis_context()
    doc = context.to_dict()
    evidence = ontogenesis_evidence(context)
    record = ontogenesis_to_platform_record(context)

    assert doc["kind"] == "OntogenesisContext"
    assert doc["sourceRepo"] == "SocioProphet/ontogenesis"
    assert "Domains/metadata.ttl" in doc["moduleRefs"]
    assert "shapes/ontogenesis.shacl.ttl" in doc["shapeRefs"]
    assert "CatalogAsset" in doc["governedRecordKinds"]
    assert "LampstandLocalSearchResult" in doc["governedRecordKinds"]
    assert "MemoryEvent" in doc["governedRecordKinds"]
    assert "shacl-validation" in doc["promotionGates"]
    assert evidence["kind"] == "OntogenesisContextEvidence"
    assert record["assetKind"] == "ontogenesis-context"
    assert "shacl" in record["compatibilitySurfaces"]


def test_cli_emits_ontogenesis_context_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "ontogenesis"
    rc = main(["emit-ontogenesis-context", "--output-dir", str(output_dir)])
    assert rc == 0

    context = json.loads((output_dir / "ontogenesis-context.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "ontogenesis-context-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "ontogenesis-platform-record.json").read_text(encoding="utf-8"))

    assert context["kind"] == "OntogenesisContext"
    assert evidence["kind"] == "OntogenesisContextEvidence"
    assert record["kind"] == "PlatformAssetRecord"
