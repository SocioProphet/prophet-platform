import json
from pathlib import Path

from lattice_surface_ingestor.cli import main
from lattice_surface_ingestor.ingest import ingest_surface

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
