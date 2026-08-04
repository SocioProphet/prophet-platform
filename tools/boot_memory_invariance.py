"""Generic gate: boot-time resident memory must not scale with durable-store size.

The 2026-08-04 compute-gateway outage was an UNBOUNDED BOOT HYDRATION — the service loaded its
whole /data store (thousands of receipts + blobs) into memory at import, so resident memory grew
with the store and OOMKilled the pod ~9s into startup, before it could serve or even log. 31
restarts, the whole gateway (compute + config-plane + governance receipts) down. Raising the
memory limit only buys headroom; the footprint still tracks store size, so it recurs as /data grows.

This harness makes the real invariant TESTABLE for any stateful service, so the anti-pattern can be
pinned instead of re-discovered in prod:

    boot-time resident memory is (approximately) INVARIANT to the number of records in the store.

Give it a `seed(store_dir, n)` that writes n records to an on-disk store, and a `boot(store_dir)`
that runs the service's hydration path against that store. It boots a SMALL store and a LARGE store
each in a FRESH interpreter (spawn — so RSS reflects that boot alone, not the parent test process),
measures peak resident memory of each, and asserts the growth is within a fixed byte budget:

    rss(large_n) - rss(small_n) <= budget_kb

Constant boot overhead (imports, interpreter) cancels in the delta; what remains is the part that
scales with the store. A hydrator that reads the whole store into RAM blows the budget (delta grows
~linearly with the record count); a lazy/bounded one keeps the delta flat. It is the executable form
of "a service must not need memory proportional to its durable store just to start."

Usage in a per-service teeth-test (pytest):

    from tools.boot_memory_invariance import assert_boot_memory_invariant

    def _seed(store, n): ...          # write n records under `store` (module-level: spawn-picklable)
    def _boot(store): ...             # run THIS service's hydrate against `store`

    def test_boot_memory_does_not_scale_with_store():
        assert_boot_memory_invariant(_seed, _boot, small_n=64, large_n=8192)
"""
from __future__ import annotations

import multiprocessing as mp
import resource
import sys
import tempfile
from pathlib import Path
from typing import Callable

# Seeds a store dir with n records; boots (hydrates) against a store dir. Both must be module-level
# functions so the `spawn` start method can pickle them into the fresh child interpreter.
SeedFn = Callable[[Path, int], None]
BootFn = Callable[[Path], None]


class BootMemoryScales(AssertionError):
    """Raised when boot RSS grows with store size beyond the budget — the OOM anti-pattern."""


def _to_kb(ru_maxrss: int) -> int:
    # getrusage reports ru_maxrss in KILOBYTES on Linux and in BYTES on macOS/BSD.
    return ru_maxrss // 1024 if sys.platform == "darwin" else ru_maxrss


def _boot_and_report(boot: BootFn, store_path: str, q: "mp.Queue") -> None:
    try:
        boot(Path(store_path))
        q.put(("ok", _to_kb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)))
    except BaseException as e:  # report, never hang the parent's q.get()
        q.put(("err", f"{type(e).__name__}: {e}"))


def measure_boot_rss_kb(boot: BootFn, store: Path, *, timeout_s: float = 120.0) -> int:
    """Boot `boot(store)` in a FRESH (spawn) interpreter and return its peak resident set (KB).

    A fresh interpreter is the whole point: the child's peak RSS reflects this boot's footprint,
    not the (already large) parent test process, so two measurements are comparable."""
    ctx = mp.get_context("spawn")
    q: "mp.Queue" = ctx.Queue()
    p = ctx.Process(target=_boot_and_report, args=(boot, str(store), q))
    p.start()
    try:
        status, value = q.get(timeout=timeout_s)
    except Exception as e:  # noqa: BLE001 — a hung/crashed child must surface, not deadlock CI
        p.terminate()
        raise RuntimeError(f"boot process did not report RSS within {timeout_s}s: {e}") from e
    finally:
        p.join(timeout=5)
    if status != "ok":
        raise RuntimeError(f"boot process failed: {value}")
    return int(value)


def assert_boot_memory_invariant(
    seed: SeedFn,
    boot: BootFn,
    *,
    small_n: int = 64,
    large_n: int = 8192,
    budget_kb: int = 8192,
) -> dict:
    """Assert boot RSS does not scale with store size.

    Seeds a store of `small_n` and one of `large_n` records, boots each in a fresh interpreter,
    and requires `rss(large_n) - rss(small_n) <= budget_kb`. Returns the measurement on success;
    raises BootMemoryScales on failure. The default 8MB budget tolerates interpreter/allocator
    noise while still catching a hydrator that pulls even a few KB per record across a ~128x
    record-count spread."""
    if large_n <= small_n:
        raise ValueError("large_n must exceed small_n for the invariance delta to mean anything")
    with tempfile.TemporaryDirectory() as ds, tempfile.TemporaryDirectory() as dl:
        small, large = Path(ds), Path(dl)
        seed(small, small_n)
        seed(large, large_n)
        rss_small = measure_boot_rss_kb(boot, small)
        rss_large = measure_boot_rss_kb(boot, large)
    delta = rss_large - rss_small
    result = {
        "small_n": small_n, "large_n": large_n,
        "rss_small_kb": rss_small, "rss_large_kb": rss_large,
        "delta_kb": delta, "budget_kb": budget_kb,
    }
    if delta > budget_kb:
        raise BootMemoryScales(
            f"boot RSS scaled with store size: {small_n} records -> {rss_small}KB, "
            f"{large_n} records -> {rss_large}KB (delta {delta}KB > budget {budget_kb}KB). "
            f"The service is hydrating its durable store into memory at boot — make it "
            f"lazy/bounded so a large store cannot OOM the pod on startup."
        )
    return result
