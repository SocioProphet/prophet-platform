import json
from pathlib import Path

from lattice_surface_ingestor.cli import main
from lattice_surface_ingestor.ingest import ingest_surface
from lattice_surface_ingestor.store import write_record_set

ROOT = Path(__file__).resolve().parents[3]


def load_contract(name: str) -> dict:
    return json.loads((ROOT / "contracts" / "lattice" / name).read_text(encoding="utf-8"))


def test_ingest_boot_release_set_contract() -> None:
    record = ingest_surface(load_contract("boot-release-set.v1.example.json"))
    assert record.asset_kind == "boot-release-set"
    assert record.producer_repo == "SourceOS-Linux/sourceos-boot"
    assert record.evidence_correlation_id == "platform-boot-demo"
    assert "prophet-platform" in record.compatibility_surfaces


def test_ingest_runtime_asset_contract() -> None:
    record = ingest_surface(load_contract("runtime-asset.v1.example.json"))
    assert record.asset_kind == "runtime-asset"
    assert record.producer_repo == "SocioProphet/lattice-forge"
    assert record.promotion_channel == "dev"
    assert "agentplane" in record.compatibility_surfaces


def test_ingestor_cli_emits_record_set(capsys) -> None:
    rc = main([
        "ingest",
        str(ROOT / "contracts" / "lattice" / "boot-release-set.v1.example.json"),
        str(ROOT / "contracts" / "lattice" / "runtime-asset.v1.example.json"),
    ])
    assert rc == 0
    emitted = json.loads(capsys.readouterr().out)
    assert emitted["kind"] == "PlatformAssetRecordSet"
    assert len(emitted["records"]) == 2


def test_ingestor_cli_writes_deterministic_record_set(tmp_path) -> None:
    output = tmp_path / "records" / "lattice-surface-records.json"
    rc = main([
        "ingest",
        str(ROOT / "contracts" / "lattice" / "boot-release-set.v1.example.json"),
        str(ROOT / "contracts" / "lattice" / "runtime-asset.v1.example.json"),
        "--output",
        str(output),
    ])
    assert rc == 0
    emitted = json.loads(output.read_text(encoding="utf-8"))
    assert emitted["apiVersion"] == "prophet.socioprophet.dev/v1"
    assert emitted["kind"] == "PlatformAssetRecordSet"
    assert [record["assetKind"] for record in emitted["records"]] == ["boot-release-set", "runtime-asset"]


def test_record_store_writes_per_asset_files(tmp_path) -> None:
    record_set = {
        "apiVersion": "prophet.socioprophet.dev/v1",
        "kind": "PlatformAssetRecordSet",
        "records": [
            ingest_surface(load_contract("boot-release-set.v1.example.json")).to_dict(),
            ingest_surface(load_contract("runtime-asset.v1.example.json")).to_dict(),
        ],
    }
    written = write_record_set(record_set, tmp_path / "store")
    names = sorted(path.name for path in written)
    assert "boot-release-set:sourceos-recovery-demo:0.1.0.json" in names
    assert "runtime-asset:prophet-python-ml:0.1.0.json" in names
    assert "manifest.json" in names


def test_store_cli_writes_per_asset_files(tmp_path) -> None:
    record_set_path = tmp_path / "record-set.json"
    output_dir = tmp_path / "store"
    main([
        "ingest",
        str(ROOT / "contracts" / "lattice" / "boot-release-set.v1.example.json"),
        str(ROOT / "contracts" / "lattice" / "runtime-asset.v1.example.json"),
        "--output",
        str(record_set_path),
    ])
    rc = main(["store", str(record_set_path), str(output_dir)])
    assert rc == 0
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "boot-release-set:sourceos-recovery-demo:0.1.0.json").exists()
    assert (output_dir / "runtime-asset:prophet-python-ml:0.1.0.json").exists()
