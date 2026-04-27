import json
from pathlib import Path

from lattice_studio.cli import main
from lattice_studio.notebook_plane import (
    demo_notebook_surface_plane,
    demo_spawn_requests,
    notebook_plane_to_platform_record,
    notebook_surface_evidence,
)

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_FIXTURES = [
    ROOT / "apps" / "lattice-studio" / "examples" / "runtime-asset.prophet-python-ml.json",
    ROOT / "contracts" / "lattice" / "runtime-asset.v1.example.json",
]


def test_notebook_surface_plane_includes_required_adapters() -> None:
    plane = demo_notebook_surface_plane()
    doc = plane.to_dict()
    adapters = {adapter["adapter"]: adapter for adapter in doc["adapters"]}

    assert doc["kind"] == "NotebookSurfacePlane"
    assert doc["defaultAdapter"] == "jupyterlab"
    assert set(adapters) == {"jupyterlab", "zeppelin", "observable", "plutojl", "quarto"}
    assert adapters["zeppelin"]["role"] == "collaborative-analytics"
    assert "spark" in adapters["zeppelin"]["capabilities"]
    assert "sql" in adapters["zeppelin"]["capabilities"]
    assert adapters["observable"]["role"] == "reactive-visualization"
    assert "browser-native-storytelling" in adapters["observable"]["capabilities"]
    assert adapters["plutojl"]["role"] == "reactive-science"
    assert "reactive-cells" in adapters["plutojl"]["capabilities"]
    assert adapters["quarto"]["role"] == "technical-publishing"
    assert "publishing" in adapters["quarto"]["capabilities"]


def test_runtime_asset_fixtures_cover_every_notebook_adapter() -> None:
    plane = demo_notebook_surface_plane()
    adapters = {adapter.adapter for adapter in plane.adapters}

    for fixture in RUNTIME_FIXTURES:
        runtime_asset = json.loads(fixture.read_text(encoding="utf-8"))
        surfaces = set(runtime_asset["spec"]["compatibility"]["surfaces"])
        assert adapters <= surfaces, f"{fixture} is missing notebook adapter surfaces: {sorted(adapters - surfaces)}"
        assert "jupyter" in surfaces, f"{fixture} must retain the legacy jupyter compatibility alias"
        assert "lattice-studio" in surfaces, f"{fixture} must advertise the Lattice Studio surface"


def test_spawn_requests_cover_every_notebook_adapter() -> None:
    requests = demo_spawn_requests()
    by_adapter = {request.adapter: request for request in requests}

    assert set(by_adapter) == {"jupyterlab", "zeppelin", "observable", "plutojl", "quarto"}
    assert by_adapter["zeppelin"].role == "collaborative-analytics"
    assert by_adapter["zeppelin"].runtime_asset_id == "runtime-asset:prophet-python-ml:0.1.0"
    assert "catalog://datasets/demo-csv@0.1.0" in by_adapter["zeppelin"].catalog_inputs


def test_notebook_surface_evidence_and_platform_record() -> None:
    plane = demo_notebook_surface_plane()
    requests = demo_spawn_requests()
    evidence = notebook_surface_evidence(plane, requests)
    record = notebook_plane_to_platform_record(plane)

    assert evidence["kind"] == "NotebookSurfaceEvidence"
    assert evidence["adapterCount"] == 5
    assert evidence["spawnRequestCount"] == 5
    assert "zeppelin-collaborative-analytics" in evidence["evidenceReports"]
    assert "quarto-reproducible-publishing" in evidence["evidenceReports"]
    assert record["kind"] == "PlatformAssetRecord"
    assert record["assetKind"] == "notebook-surface-plane"
    assert "zeppelin" in record["compatibilitySurfaces"]
    assert "quarto" in record["compatibilitySurfaces"]


def test_cli_emits_notebook_surface_plane_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "notebook-plane"
    rc = main(["emit-notebook-plane", "--output-dir", str(output_dir)])
    assert rc == 0

    plane = json.loads((output_dir / "notebook-surface-plane.json").read_text(encoding="utf-8"))
    requests = json.loads((output_dir / "notebook-spawn-requests.json").read_text(encoding="utf-8"))
    evidence = json.loads((output_dir / "notebook-surface-evidence.json").read_text(encoding="utf-8"))
    record = json.loads((output_dir / "notebook-plane-platform-record.json").read_text(encoding="utf-8"))

    assert plane["kind"] == "NotebookSurfacePlane"
    assert requests["kind"] == "NotebookSurfaceSpawnRequestSet"
    assert len(requests["requests"]) == 5
    assert evidence["kind"] == "NotebookSurfaceEvidence"
    assert record["kind"] == "PlatformAssetRecord"
