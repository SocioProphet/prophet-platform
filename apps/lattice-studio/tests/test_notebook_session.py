import json
from pathlib import Path

from lattice_studio.cli import main
from lattice_studio.session import create_session, evidence_for_session, load_json

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_ASSET = ROOT / "apps" / "lattice-studio" / "examples" / "runtime-asset.prophet-python-ml.json"


def test_create_session_binds_runtime_and_catalog_inputs() -> None:
    runtime_asset = load_json(RUNTIME_ASSET)
    session = create_session(
        project_id="demo-project",
        user_id="demo-user",
        runtime_asset=runtime_asset,
        catalog_inputs=["catalog://datasets/demo-csv"],
        policy_ref="policy://lattice-studio/demo",
    )

    assert session.runtime_asset_id == "runtime-asset:prophet-python-ml:0.1.0"
    assert session.kernel_name == "prophet-python-ml-0.1.0"
    assert session.catalog_inputs == ["catalog://datasets/demo-csv"]
    assert session.policy_ref == "policy://lattice-studio/demo"


def test_session_evidence_links_runtime_project_user_and_digest() -> None:
    runtime_asset = load_json(RUNTIME_ASSET)
    session = create_session(project_id="demo-project", user_id="demo-user", runtime_asset=runtime_asset)
    evidence = evidence_for_session(session)

    assert evidence["kind"] == "NotebookSessionEvidence"
    assert evidence["sessionId"] == session.session_id
    assert evidence["runtimeAssetId"] == session.runtime_asset_id
    assert evidence["sessionDigest"].startswith("sha256:")
    assert "runtime-binding" in evidence["evidenceReports"]


def test_lattice_studio_cli_writes_session_bundle(tmp_path) -> None:
    output_dir = tmp_path / "session"
    rc = main([
        "create-session",
        "--project-id",
        "demo-project",
        "--user-id",
        "demo-user",
        "--runtime-asset",
        str(RUNTIME_ASSET),
        "--catalog-input",
        "catalog://datasets/demo-csv",
        "--policy-ref",
        "policy://lattice-studio/demo",
        "--output-dir",
        str(output_dir),
    ])
    assert rc == 0
    session_doc = json.loads((output_dir / "notebook-session.json").read_text(encoding="utf-8"))
    evidence_doc = json.loads((output_dir / "notebook-session-evidence.json").read_text(encoding="utf-8"))
    assert session_doc["kind"] == "NotebookSession"
    assert evidence_doc["kind"] == "NotebookSessionEvidence"
