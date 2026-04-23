from services.wopi_host.app.store import InMemoryWOPIStore


def test_store_lock_and_writeback_state() -> None:
    store = InMemoryWOPIStore()

    locked = store.acquire_lock("demo-doc")
    assert locked.document_id == "demo-doc"
    assert locked.lock_token == "lock-demo-doc"
    assert locked.version_counter == 0

    written = store.writeback("demo-doc")
    assert written.document_id == "demo-doc"
    assert written.version_counter == 1

    fetched = store.get("demo-doc")
    assert fetched is not None
    assert fetched.version_counter == 1
