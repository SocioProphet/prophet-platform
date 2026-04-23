from pathlib import Path

from services.wopi_host.app.file_store import FileBackedWOPIStore


def test_file_backed_store_persists_state(tmp_path: Path) -> None:
    store = FileBackedWOPIStore(tmp_path)

    locked = store.acquire_lock("demo-doc")
    assert locked.lock_token == "lock-demo-doc"
    assert (tmp_path / "demo-doc.json").exists()

    written = store.writeback("demo-doc")
    assert written.version_counter == 1

    fetched = store.get("demo-doc")
    assert fetched is not None
    assert fetched.version_counter == 1
