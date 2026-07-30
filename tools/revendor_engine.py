#!/usr/bin/env python3
"""Execute a disciplined engine re-vendor and seal each step into a receipt.

The consumer-side executor of the vendor-freshness plane. sociosphere's detector emits an
EffectRequest; the membrane approves it; THIS acts on the approval — and it treats every
step of the re-vendor discipline (vendor-freshness-plane.md § Re-vendor discipline) as a
claim it must PROVE, not a command it may assume worked. The deliverable is a re-vendor PR
whose body *is* the receipt: which tarball (by digest), which marker proved it is that
release, which files moved, the floor it raised, and the guard's own verdict. A re-vendor
that cannot show its work is the stale-dist-under-a-fresh-version-string regression this
plane exists to stop.

Three properties it holds because each has a failure mode that has actually happened here:

* Fail-closed. Any step whose proof does not hold aborts the whole operation, leaving a
  receipt that records exactly where it stopped. Nothing half-applied; no PR on a broken
  proof. (The opposite — a guard that fails and is ignored — is VFP-0001.)
* Atomic across consumers. hellgraph-service and lifecycle-warden MUST track the same
  engine release; lifecycle-warden once drifted five releases behind unnoticed because a
  re-vendor moved one and not the other. The tarball and the floor move for ALL consumers
  in one change or not at all.
* Idempotent. Keyed on to_version. If every consumer already ships it (tarball present,
  marker proven, floor at or above it) the run is a no-op that says so — a re-emitted
  finding must never open a second PR.

Default is dry-run: it computes the plan and the receipt and mutates nothing. --apply
performs the file changes; --open-pr additionally opens the (idempotent) re-vendor PR.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _load_marker_tool():
    """Reuse the verified marker assertion rather than reimplement byte-containment."""
    spec = importlib.util.spec_from_file_location(
        "assert_vendored_engine_marker", _HERE / "assert_vendored_engine_marker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


marker_tool = _load_marker_tool()

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class RevendorAbort(Exception):
    """A discipline step could not be proven. Carries the failed step's evidence so the
    receipt records precisely where and why the re-vendor stopped."""

    def __init__(self, step: str, reason: str, evidence: dict | None = None):
        super().__init__(f"{step}: {reason}")
        self.step = step
        self.reason = reason
        self.evidence = evidence or {}


def _semver_key(v: str) -> tuple[int, int, int]:
    return tuple(int(p) for p in v.split("."))  # type: ignore[return-value]


@dataclass
class RevendorPlan:
    """What to re-vendor to, and how to prove it. Derived from an approved EffectRequest,
    or given directly for a manual/tested run."""
    to_version: str
    tarball: Path
    expect_markers: list[str]
    consumers: list[str] = field(default_factory=lambda: ["hellgraph-service", "lifecycle-warden"])
    forbid_markers: list[str] = field(default_factory=list)
    member: str = marker_tool.DEFAULT_MEMBER
    requested_by_event_ref: str | None = None

    @property
    def idempotency_key(self) -> str:
        return f"engine@{self.to_version}"

    def __post_init__(self):
        if not SEMVER.match(self.to_version):
            raise ValueError(f"to_version must be X.Y.Z, got {self.to_version!r}")
        self.tarball = Path(self.tarball)
        if not self.expect_markers:
            raise ValueError("at least one expect marker is required — a version field is not evidence")

    @classmethod
    def from_effect_request(cls, doc: dict) -> "RevendorPlan":
        """Build from the EffectRequest the plane emits (schema specVersion 0.1.0):
        capability vendor.revendor, parameters carry from/to versions, the register's
        version_marker rides in parameters.expectMarkers."""
        if doc.get("capability") != "vendor.revendor":
            raise ValueError(f"not a vendor.revendor EffectRequest (capability={doc.get('capability')!r})")
        p = doc.get("parameters", {})
        markers = p.get("expectMarkers") or ([p["versionMarker"]] if p.get("versionMarker") else [])
        return cls(
            to_version=p["toVersion"],
            tarball=Path(p["tarball"]),
            expect_markers=list(markers),
            forbid_markers=list(p.get("forbidMarkers", [])),
            consumers=list(p.get("consumers", ["hellgraph-service", "lifecycle-warden"])),
            requested_by_event_ref=doc.get("requestedByEventRef"),
        )


# ── the artifacts the executor reads and rewrites ────────────────────────────────────

def _pkg_path(root: Path, consumer: str) -> Path:
    return root / "apps" / consumer / "package.json"


def _guard_path(root: Path, consumer: str) -> Path:
    return root / "apps" / consumer / "scripts" / "check-engine-version.mjs"


def _vendored_ref(root: Path, consumer: str) -> tuple[str | None, str | None]:
    """Return (dependency spec, pinned version) for the engine dep, or (None, None)."""
    pkg = json.loads(_pkg_path(root, consumer).read_text())
    spec = pkg.get("dependencies", {}).get("@socioprophet/hellgraph")
    if not spec:
        return None, None
    m = re.search(r"socioprophet-hellgraph-(\d+\.\d+\.\d+)\.tgz", spec) or re.search(r"#v?(\d+\.\d+\.\d+)$", spec)
    return spec, (m.group(1) if m else None)


def _current_floor(root: Path, consumer: str) -> str | None:
    m = re.search(r"const MIN_ENGINE = '(\d+\.\d+\.\d+)'", _guard_path(root, consumer).read_text())
    return m.group(1) if m else None


# ── the disciplined steps, each returning evidence or raising RevendorAbort ───────────

def step_assert_marker(plan: RevendorPlan) -> dict:
    """Discipline step 2: prove the tarball's packed dist carries the discriminating
    marker. A version field is not evidence; the bundle is."""
    if not plan.tarball.exists():
        raise RevendorAbort("assert_marker", f"tarball not found: {plan.tarball}")
    # Copilot #1062 round 2: marker_tool.read_member raises SystemExit for the
    # artifact-is-not-what-it-claims cases (unreadable gzip, missing member,
    # non-file member, declared-size-over-cap, expanded-past-cap). SystemExit
    # inherits from BaseException, so execute()'s `except RevendorAbort` lets it
    # tear the whole run down WITHOUT a sealed receipt — the exact opposite of
    # this executor's fail-closed-AND-receipt-producing contract. Convert to a
    # RevendorAbort here so a corrupt tarball becomes a receipt saying
    # assert_marker.ok=false with the reader's own error text as evidence.
    try:
        raw = marker_tool.read_member(plan.tarball, plan.member)  # bounded, typed read
    except SystemExit as exc:
        raise RevendorAbort(
            "assert_marker",
            f"tarball could not be read as a packed dist: {exc}",
            {"tarball": str(plan.tarball), "member": plan.member,
             "reader_error": str(exc)},
        )
    missing = [m for m in plan.expect_markers if m.encode("utf-8") not in raw]
    present_forbidden = [m for m in plan.forbid_markers if m.encode("utf-8") in raw]
    digest = marker_tool.sha256_file(plan.tarball)
    evidence = {
        "tarball_digest": f"sha256:{digest}", "member": plan.member,
        "expected_present": plan.expect_markers, "forbidden_absent": plan.forbid_markers,
    }
    if missing or present_forbidden:
        raise RevendorAbort("assert_marker",
                            f"marker proof failed (missing={missing}, forbidden_present={present_forbidden})",
                            evidence)
    return evidence


def step_precheck(plan: RevendorPlan, root: Path) -> dict:
    """Read-only validation of every consumer BEFORE any file is touched, so a violation
    (a missing dep, a floor that would move backwards) aborts with nothing half-applied.
    place_tarball and bump_floor keep their own checks as defense-in-depth, but this is
    where fail-closed is actually enforced across the atomic set."""
    per_consumer = {}
    for consumer in plan.consumers:
        spec, ver = _vendored_ref(root, consumer)
        if spec is None:
            raise RevendorAbort("precheck", f"{consumer} has no @socioprophet/hellgraph dependency")
        floor = _current_floor(root, consumer)
        if floor is None:
            raise RevendorAbort("precheck", f"{consumer} guard has no MIN_ENGINE constant")
        if _semver_key(plan.to_version) < _semver_key(floor):
            raise RevendorAbort("precheck",
                                f"{consumer} floor {floor} is already above target {plan.to_version} — "
                                f"a re-vendor moves forward or aborts; refusing to lower a floor")
        per_consumer[consumer] = {"current_version": ver, "current_floor": floor}
    return {"consumers": per_consumer}


def step_place_tarball(plan: RevendorPlan, root: Path, apply: bool) -> dict:
    """Discipline step: place the tarball and repoint the dep, for every consumer, so the
    ref, filename and internal version all agree (what check-engine-version.mjs enforces)."""
    new_name = f"socioprophet-hellgraph-{plan.to_version}.tgz"
    per_consumer = {}
    for consumer in plan.consumers:
        old_spec, old_ver = _vendored_ref(root, consumer)
        if old_spec is None:
            raise RevendorAbort("place_tarball", f"{consumer} has no @socioprophet/hellgraph dependency")
        vendor_dir = root / "apps" / consumer / "vendor"
        new_ref = f"file:vendor/{new_name}"
        removed = []
        if apply:
            vendor_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(plan.tarball, vendor_dir / new_name)
            for old in vendor_dir.glob("socioprophet-hellgraph-*.tgz"):
                if old.name != new_name:
                    old.unlink()
                    removed.append(old.name)
            pkg_file = _pkg_path(root, consumer)
            pkg = json.loads(pkg_file.read_text())
            pkg["dependencies"]["@socioprophet/hellgraph"] = new_ref
            pkg_file.write_text(json.dumps(pkg, indent=2) + "\n")
        per_consumer[consumer] = {"old_ref": old_spec, "new_ref": new_ref,
                                  "old_version": old_ver, "removed": removed}
    return {"new_tarball": new_name, "consumers": per_consumer}


def step_bump_floor(plan: RevendorPlan, root: Path, apply: bool) -> dict:
    """Discipline step 3: raise MIN_ENGINE for every consumer so the floor moves with the
    tarball. Never LOWERS a floor — a re-vendor is a move forward or an abort."""
    per_consumer = {}
    for consumer in plan.consumers:
        old = _current_floor(root, consumer)
        if old is None:
            raise RevendorAbort("bump_floor", f"{consumer} guard has no MIN_ENGINE constant")
        if _semver_key(plan.to_version) < _semver_key(old):
            raise RevendorAbort("bump_floor",
                                f"{consumer} floor {old} is already above target {plan.to_version} — "
                                f"refusing to lower it")
        if apply and old != plan.to_version:
            gp = _guard_path(root, consumer)
            gp.write_text(re.sub(r"const MIN_ENGINE = '\d+\.\d+\.\d+'",
                                 f"const MIN_ENGINE = '{plan.to_version}'", gp.read_text(), count=1))
        per_consumer[consumer] = {"old_floor": old, "new_floor": plan.to_version}
    return {"consumers": per_consumer}


def step_verify_guard(plan: RevendorPlan, root: Path) -> dict:
    """Run each consumer's own guard against the applied state. The guard re-checks the
    ref/filename/internal-version agreement and the floor from scratch — the executor does
    not get to grade its own work."""
    per_consumer = {}
    for consumer in plan.consumers:
        gp = _guard_path(root, consumer)
        proc = subprocess.run(["node", str(gp)], capture_output=True, text=True, timeout=60)
        per_consumer[consumer] = {"exit": proc.returncode,
                                  "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
        if proc.returncode != 0:
            raise RevendorAbort("verify_guard", f"{consumer} guard rejected the re-vendor",
                                per_consumer[consumer])
    return {"consumers": per_consumer}


def _already_current(plan: RevendorPlan, root: Path) -> bool:
    """True only if EVERY consumer already ships to_version with the marker proven and the
    floor at or above it — the idempotency guard."""
    for consumer in plan.consumers:
        _, ver = _vendored_ref(root, consumer)
        floor = _current_floor(root, consumer)
        if ver != plan.to_version or floor is None or _semver_key(floor) < _semver_key(plan.to_version):
            return False
        tgz = root / "apps" / consumer / "vendor" / f"socioprophet-hellgraph-{plan.to_version}.tgz"
        if not tgz.exists():
            return False
        try:
            raw = marker_tool.read_member(tgz, plan.member)
        except SystemExit:
            return False
        if any(m.encode("utf-8") not in raw for m in plan.expect_markers):
            return False
    return True


def _seal(receipt: dict) -> dict:
    """Tamper-evident seal: a digest over the canonical receipt body. Any later edit to a
    step or its evidence changes the digest."""
    body = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    receipt["receipt_digest"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return receipt


def _capture_pre_state(plan: RevendorPlan, root: Path) -> dict:
    """Snapshot every file the mutation steps (place_tarball, bump_floor) can touch, so a
    failure AFTER a mutation — including verify_guard, which runs against applied files —
    can be rolled back to leave nothing half-applied. Copilot #1062: verify_guard failing
    used to leave the copied tarball, the unlinked old tarball, the bumped package.json and
    the bumped guard on disk while reporting status=failed."""
    files: dict[str, bytes] = {}
    vendor_dirs: list[Path] = []
    pre_vendor: dict[str, set[str]] = {}
    for consumer in plan.consumers:
        vendor_dir = root / "apps" / consumer / "vendor"
        vendor_dirs.append(vendor_dir)
        present = set()
        if vendor_dir.is_dir():
            for f in vendor_dir.iterdir():
                if f.is_file():
                    files[str(f)] = f.read_bytes()
                    present.add(f.name)
        pre_vendor[str(vendor_dir)] = present
        for p in (_pkg_path(root, consumer), _guard_path(root, consumer)):
            if p.exists():
                files[str(p)] = p.read_bytes()
    return {"files": files, "vendor_dirs": [str(d) for d in vendor_dirs], "pre_vendor": pre_vendor}


def _rollback(state: dict) -> None:
    """Restore the captured pre-mutation state: rewrite every snapshotted file (reverting
    package.json/guard and recreating any unlinked old tarball) and delete any vendor file
    the run created (the new tarball). Idempotent."""
    for path_str, data in state["files"].items():
        p = Path(path_str)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    for d_str in state["vendor_dirs"]:
        d = Path(d_str)
        if not d.is_dir():
            continue
        keep = state["pre_vendor"].get(d_str, set())
        for f in d.iterdir():
            if f.is_file() and f.name not in keep:
                f.unlink()


def execute(plan: RevendorPlan, root: Path, apply: bool = False) -> dict:
    """Run the disciplined re-vendor. Returns a sealed receipt. Fail-closed AND atomic under
    apply: read-only proofs (marker, precheck) run before any mutation, and if a later step
    fails — including verify_guard, which necessarily runs against the mutated files — every
    mutation is rolled back, so a failed run leaves NOTHING half-applied. In dry-run
    (apply=False) no file is touched."""
    receipt: dict = {
        "tool": "prophet-platform.revendor_engine.v1",
        "idempotency_key": plan.idempotency_key,
        "to_version": plan.to_version,
        "consumers": plan.consumers,
        "requested_by_event_ref": plan.requested_by_event_ref,
        "mode": "apply" if apply else "dry-run",
        "steps": [],
    }

    def record(step: str, ok: bool, evidence: dict):
        receipt["steps"].append({"step": step, "ok": ok, "evidence": evidence})

    # Marker proof first: it never mutates and it is the gate on everything after it.
    try:
        record("assert_marker", True, step_assert_marker(plan))
    except RevendorAbort as abort:
        record(abort.step, False, {"reason": abort.reason, **abort.evidence})
        receipt["status"] = "failed"
        return _seal(receipt)

    if _already_current(plan, root):
        receipt["status"] = "noop"
        receipt["note"] = "every consumer already ships this release with the marker proven and the floor raised"
        return _seal(receipt)

    # All read-only proofs must hold before the first mutation (fail-closed across the set).
    try:
        record("precheck", True, step_precheck(plan, root))
    except RevendorAbort as abort:
        record(abort.step, False, {"reason": abort.reason, **abort.evidence})
        receipt["status"] = "failed"
        return _seal(receipt)

    # Capture the pre-mutation state so any failure below rolls back to it (apply only).
    pre_state = _capture_pre_state(plan, root) if apply else None
    for step_fn, name in ((step_place_tarball, "place_tarball"), (step_bump_floor, "bump_floor")):
        try:
            record(name, True, step_fn(plan, root, apply))
        except RevendorAbort as abort:
            if apply:
                _rollback(pre_state)
            record(abort.step, False,
                   {"reason": abort.reason, "rolled_back": bool(apply), **abort.evidence})
            receipt["status"] = "failed"
            return _seal(receipt)

    # The guard only means something against applied files — and it runs AFTER the
    # mutations, so its failure must undo them too, or the tree is left half-applied.
    if apply:
        try:
            record("verify_guard", True, step_verify_guard(plan, root))
        except RevendorAbort as abort:
            _rollback(pre_state)
            record(abort.step, False, {"reason": abort.reason, "rolled_back": True, **abort.evidence})
            receipt["status"] = "failed"
            return _seal(receipt)

    receipt["status"] = "applied" if apply else "planned"
    return _seal(receipt)


# ── PR emission (idempotent) ─────────────────────────────────────────────────────────

def _paths_this_revendor_mutates(plan: RevendorPlan, root: Path) -> list[Path]:
    """The EXACT files a successful re-vendor of `plan` touches — the new tgz (untracked),
    any old tgz(s) unlinked, package.json and the guard for each consumer. Enumerating them
    is what lets us `git add` them explicitly rather than `git commit -a` (Copilot #1062:
    -a misses the untracked new tgz entirely — the PR would delete the old tgz + bump
    package.json but never carry the new bytes it points at — and risks sweeping in
    unrelated tracked changes)."""
    paths: list[Path] = []
    for consumer in plan.consumers:
        vendor_dir = root / "apps" / consumer / "vendor"
        paths.append(vendor_dir / f"socioprophet-hellgraph-{plan.to_version}.tgz")
        # Any other tgz in vendor/ was unlinked by step_place_tarball; adding the whole
        # directory (post-mutation state) captures both the new file and the deletions.
        paths.append(vendor_dir)
        paths.append(_pkg_path(root, consumer))
        paths.append(_guard_path(root, consumer))
    return paths


def open_pr(plan: RevendorPlan, receipt: dict, root: Path) -> dict:
    """Open the re-vendor PR whose body is the receipt. Idempotent on the branch name
    (derived from the idempotency key): if the branch already exists, do not open a second
    PR. Requires an applied receipt."""
    if receipt.get("status") != "applied":
        raise RevendorAbort("open_pr", f"refusing to open a PR for a {receipt.get('status')} receipt")
    branch = f"revendor/engine-{plan.to_version}"
    existing = subprocess.run(["git", "-C", str(root), "ls-remote", "--heads", "origin", branch],
                              capture_output=True, text=True).stdout.strip()
    if existing:
        return {"opened": False, "reason": "branch already exists — idempotent no-op", "branch": branch}
    body = "```json\n" + json.dumps(receipt, indent=2) + "\n```"
    subprocess.run(["git", "-C", str(root), "switch", "-c", branch], check=True)
    # Copilot #1062: `git commit -a` (a) does NOT stage new files, so the freshly-copied
    # tarball would be committed-around, and (b) sweeps in any unrelated tracked change
    # in the working tree. Stage the exact paths this run mutated, then commit without -a.
    mutated = [str(p.relative_to(root)) for p in _paths_this_revendor_mutates(plan, root)]
    subprocess.run(["git", "-C", str(root), "add", "--", *mutated], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm",
                    f"chore(revendor): engine → {plan.to_version} (marker-proven, guard-verified)"], check=True)
    subprocess.run(["git", "-C", str(root), "push", "-u", "origin", branch], check=True)
    subprocess.run(["gh", "pr", "create", "--fill-first", "--body", body, "--head", branch], check=True, cwd=root)
    return {"opened": True, "branch": branch, "staged_paths": mutated}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Execute a disciplined, receipt-sealed engine re-vendor.")
    ap.add_argument("--from-effect-request", type=Path, help="an approved vendor.revendor EffectRequest JSON")
    ap.add_argument("--to-version")
    ap.add_argument("--tarball", type=Path)
    ap.add_argument("--expect", action="append", default=[], metavar="MARKER")
    ap.add_argument("--forbid", action="append", default=[], metavar="MARKER")
    ap.add_argument("--consumer", action="append", default=[], help="repeatable; default both engine consumers")
    ap.add_argument("--root", type=Path, default=_HERE.parent, help="repo root (default: this repo)")
    ap.add_argument("--apply", action="store_true", help="perform the file changes (default: dry-run)")
    ap.add_argument("--open-pr", action="store_true", help="open the idempotent re-vendor PR (implies --apply)")
    args = ap.parse_args(argv)

    if args.from_effect_request:
        plan = RevendorPlan.from_effect_request(json.loads(args.from_effect_request.read_text()))
    elif args.to_version and args.tarball:
        plan = RevendorPlan(to_version=args.to_version, tarball=args.tarball, expect_markers=args.expect,
                            forbid_markers=args.forbid,
                            consumers=args.consumer or ["hellgraph-service", "lifecycle-warden"])
    else:
        ap.error("provide --from-effect-request, or both --to-version and --tarball")

    apply = args.apply or args.open_pr
    receipt = execute(plan, args.root, apply=apply)
    if receipt["status"] == "applied" and args.open_pr:
        # Copilot #1062 round 2: the receipt IS the deliverable. If open_pr raises
        # (RevendorAbort for a non-applied state, subprocess.CalledProcessError from
        # any of git switch/add/commit/push or gh pr create, or OSError on a broken
        # git tree) and we let it propagate, main() exits before printing — and
        # automation loses the final JSON status entirely. Record the failure as a
        # regular step, demote to failed, re-seal, print. Exit 1 still signals the
        # operation failed, but a downstream `jq` on stdout has the whole story.
        try:
            receipt["pr"] = open_pr(plan, receipt, args.root)
        except (RevendorAbort, subprocess.CalledProcessError, OSError) as exc:
            step = getattr(exc, "step", "open_pr")
            reason = getattr(exc, "reason", None) or str(exc)
            evidence: dict = dict(getattr(exc, "evidence", {}) or {})
            if isinstance(exc, subprocess.CalledProcessError):
                evidence.update({"argv": list(exc.cmd) if exc.cmd else [],
                                 "returncode": exc.returncode})
            receipt["steps"].append({"step": step, "ok": False,
                                     "evidence": {"reason": reason, **evidence}})
            receipt["status"] = "failed"
        _seal(receipt)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] in ("applied", "planned", "noop") else 1


if __name__ == "__main__":
    raise SystemExit(main())
