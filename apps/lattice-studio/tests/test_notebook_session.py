import json
from pathlib import Path

from lattice_studio.catalog import catalog_evidence, demo_catalog_assets
from lattice_studio.cli import main
from lattice_studio.platform_records import catalog_asset_to_platform_record, notebook_session_to_platform_record, platform_record_set
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


def test_demo_catalog_assets_cover_data_ml_application_and_service() -> None:
    assets = demo_catalog_assets()
    by_type = {asset.asset_type: asset for asset in assets}

    assert set(by_type) == {"data", "ml-model", "application", "service"}
    assert by_type["data"].latest_version.runtime_asset_refs == ["runtime-asset:prophet-python-ml:0.1.0"]
    assert by_type["ml-model"].latest_version.dataset_refs == ["catalog://datasets/demo-csv@0.1.0"]
    assert by_type["application"].latest_version.model_refs == ["catalog://models/demo-classifier@0.1.0"]
    assert by_type["service"].latest_version.application_refs == ["catalog://applications/demo-notebook-app@0.1.0"]


def test_catalog_evidence_is_digest_backed_and_zenodo_ck_informed() -> None:
    for asset in demo_catalog_assets():
        doc = asset.to_dict()
        evidence = catalog_evidence(asset)
        assert doc["kind"] == "CatalogAsset"
        assert doc["assetType"] in {"data", "ml-model", "application", "service"}
        assert doc["conceptPersistentId"].startswith("doi:")
        assert doc["latestVersion"]["versionPersistentId"].startswith("doi:")
        assert doc["latestVersion"]["immutableAfterPublication"] is True
        assert doc["latestVersion"]["automation"]["reproduceCommand"]
        assert evidence["assetDigest"].startswith("sha256:")
        assert "linked-runtime-data-model-application-service-assets" in evidence["evidenceReports"]


def test_lattice_studio_cli_writes_demo_catalog_bundles(tmp_path) -> None:
    output_dir = tmp_path / "catalog"
    rc = main(["emit-demo-catalog", "--output-dir", str(output_dir)])
    assert rc == 0

    expected_dirs = {
        "datasets_demo-csv",
        "models_demo-classifier",
        "applications_demo-notebook-app",
        "services_demo-inference-service",
    }
    assert expected_dirs == {path.name for path in output_dir.iterdir() if path.is_dir()}
    for asset_dir in output_dir.iterdir():
        if not asset_dir.is_dir():
            continue
        asset_doc = json.loads((asset_dir / "catalog-asset.json").read_text(encoding="utf-8"))
        evidence_doc = json.loads((asset_dir / "catalog-asset-evidence.json").read_text(encoding="utf-8"))
        assert asset_doc["kind"] == "CatalogAsset"
        assert evidence_doc["kind"] == "CatalogAssetEvidence"


def test_studio_outputs_convert_to_platform_asset_records() -> None:
    catalog_records = [catalog_asset_to_platform_record(asset.to_dict()) for asset in demo_catalog_assets()]
    runtime_asset = load_json(RUNTIME_ASSET)
    session = create_session(
        project_id="demo-project",
        user_id="demo-user",
        runtime_asset=runtime_asset,
        catalog_inputs=["catalog://datasets/demo-csv@0.1.0"],
    )
    session_record = notebook_session_to_platform_record(session.to_dict())
    record_set = platform_record_set([*catalog_records, session_record])

    assert record_set["kind"] == "PlatformAssetRecordSet"
    assert len(record_set["records"]) == 5
    kinds = {record["assetKind"] for record in record_set["records"]}
    assert {"catalog-data", "catalog-ml-model", "catalog-application", "catalog-service", "notebook-session"} == kinds


def test_lattice_studio_cli_emits_platform_records(tmp_path) -> None:
    catalog_dir = tmp_path / "catalog"
    session_dir = tmp_path / "session"
    records_path = tmp_path / "studio-platform-records.json"
    assert main(["emit-demo-catalog", "--output-dir", str(catalog_dir)]) == 0
    assert main([
        "create-session",
        "--project-id",
        "demo-project",
        "--user-id",
        "demo-user",
        "--runtime-asset",
        str(RUNTIME_ASSET),
        "--catalog-input",
        "catalog://datasets/demo-csv@0.1.0",
        "--output-dir",
        str(session_dir),
    ]) == 0
    catalog_asset_paths = sorted(str(path) for path in catalog_dir.glob("*/catalog-asset.json"))
    args = ["emit-platform-records"]
    for path in catalog_asset_paths:
        args.extend(["--catalog-asset", path])
    args.extend(["--notebook-session", str(session_dir / "notebook-session.json"), "--output", str(records_path)])
    assert main(args) == 0
    emitted = json.loads(records_path.read_text(encoding="utf-8"))
    assert emitted["kind"] == "PlatformAssetRecordSet"
    assert len(emitted["records"]) == 5
