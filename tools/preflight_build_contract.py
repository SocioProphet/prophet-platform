#!/usr/bin/env python3
"""Build-contract preflight — the sibling of preflight_deploy_contract.py, one layer down.

The deploy contract already guarantees that what we DEPLOY is immutable: no moving tags, no
omitted tags, no foreign registries. It stops at the image reference. This gate covers what
we BUILD FROM, because a sha-pinned image tag is a reproducible IDENTIFIER, not a reproducible
BUILD: `FROM python:3.12-slim` plus `fastapi>=0.110` means rebuilding the same commit next
month yields a different dependency closure, and nothing anywhere records which closure a
given running image actually contains.

That gap is not hypothetical for this estate. `cryptography>=42.0` is unbounded on
compute-gateway — the service that mounts the masking PDP, i.e. the service whose whole claim
is that its cryptographic behaviour is provable.

Checks:
  1. Every first-party Dockerfile pins each base image by DIGEST (`FROM img:tag@sha256:...`).
     A tag is a mutable pointer; `python:3.12-slim` today and in six months are different
     images with the same name.
  2. Every app requirements file is fully pinned (`==` on every requirement). A range is a
     decision deferred to build time, made by whoever happens to build.
  3. RATCHET INTEGRITY — an entry that no longer violates must be REMOVED. The ratchet only
     shrinks; a fixed entry left behind would silently re-permit the violation.

--heal does the mechanical fix rather than describing it: `docker manifest inspect` to resolve
a tag to its current digest, `uv pip compile` to freeze a requirements range into pins. A gate
that can only say "no" is a detector, and the estate has enough detectors.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RATCHET_PATH = ROOT / "tools" / "build_contract_ratchet.json"

FROM_RE = re.compile(r"^\s*FROM\s+(?!--)(\S+)", re.IGNORECASE | re.MULTILINE)
# A requirement line that pins exactly. Everything else (>=, ~=, bare name, <) is a range.
PINNED_RE = re.compile(r"^[A-Za-z0-9._-]+(\[[^\]]+\])?\s*==\s*\S+")
SKIP_LINE = re.compile(r"^\s*(#|-r\s|--|$)")


def dockerfiles() -> list[Path]:
    return sorted(p for p in ROOT.glob("apps/*/Dockerfile") if p.is_file())


def requirement_files() -> list[Path]:
    return sorted(p for p in ROOT.glob("apps/*/requirements.txt") if p.is_file())


def unpinned_bases(df: Path) -> list[str]:
    """Base images referenced without a digest. Multi-stage `AS` aliases are not images."""
    aliases: set[str] = set()
    out: list[str] = []
    for line in df.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*FROM\s+(?!--)(\S+)(?:\s+AS\s+(\S+))?", line, re.IGNORECASE)
        if not m:
            continue
        ref, alias = m.group(1), m.group(2)
        if alias:
            aliases.add(alias.lower())
        if ref.lower() in aliases:
            continue  # referring to an earlier stage, not pulling an image
        # `scratch` is the empty base, not a pulled image: there is nothing to pin and
        # `docker manifest inspect scratch` cannot succeed. Excluding it is correctness, not
        # an exemption — treating it as unpinnable would strand every distroless build.
        if ref.lower() == "scratch":
            continue
        if "@sha256:" not in ref:
            out.append(ref)
    return out


def lock_is_live(rf: Path) -> bool:
    """A hash-pinned lock counts ONLY if the build actually installs from it.

    A requirements.lock sitting beside a Dockerfile that still runs
    `pip install -r requirements.txt` resolves nothing at build time — it is a file that
    looks like a fix. So conformance requires the lock to exist AND the Dockerfile to
    install it under --require-hashes.
    """
    lock = rf.with_name("requirements.lock")
    df = rf.parent / "Dockerfile"
    if not lock.exists():
        return False
    if not df.exists():
        return True  # no image is built here; the lock is the whole pin
    text = df.read_text(encoding="utf-8", errors="replace")
    return "requirements.lock" in text and "--require-hashes" in text


def unpinned_requirements(rf: Path) -> list[str]:
    if lock_is_live(rf):
        return []
    out: list[str] = []
    for line in rf.read_text(encoding="utf-8", errors="replace").splitlines():
        if SKIP_LINE.match(line):
            continue
        if not PINNED_RE.match(line.strip()):
            out.append(line.strip())
    return out


def lock_install_is_reachable(df: Path) -> str | None:
    """A --require-hashes install must target a path some COPY actually creates.

    Renaming only the COPY source yields `COPY requirements.lock ./requirements.txt` plus
    `pip install -r requirements.lock`: an install of a file that was never created. The
    image build fails, but only at build time and only for that one service — this makes it
    a static check so the whole estate is covered by the gate rather than by luck.
    """
    text = df.read_text(encoding="utf-8", errors="replace")
    if "--require-hashes" not in text:
        return None
    targets = re.findall(r"pip install[^\n]*?--require-hashes[^\n]*?-r\s+(\S+)", text)
    copies = re.findall(r"^COPY\s+(?:--\S+\s+)*(\S+)\s+(\S+)\s*$", text, re.MULTILINE)
    for tgt in targets:
        name = tgt.rsplit("/", 1)[-1]
        ok = False
        for src, dst in copies:
            # `COPY x ./` keeps the source filename; `COPY x ./y` names it y.
            landed = src.rsplit("/", 1)[-1] if dst.endswith("/") else dst.rsplit("/", 1)[-1]
            if landed == name:
                ok = True
                break
        if not ok:
            return f"installs {tgt!r} but no COPY creates it"
    return None


def load_ratchet() -> dict:
    if not RATCHET_PATH.exists():
        return {"unpinned_base_images": {}, "unpinned_requirements": {}}
    return json.loads(RATCHET_PATH.read_text(encoding="utf-8"))


def resolve_digest(ref: str, attempts: int = 4) -> str | None:
    """Resolve a tag to its immutable digest. Requires network + docker.

    Retries with backoff: Docker Hub rate-limits and times out, which is the exact fragility
    this gate exists to remove, and it was failing the healer itself. One transient 429 should
    not leave an image unpinned forever.
    """
    import time
    for i in range(attempts):
        out = _try_manifest(ref)
        if out is not None:
            return out
        if i < attempts - 1:
            time.sleep(2 ** i * 3)
    return None


def _try_manifest(ref: str) -> str | None:
    try:
        out = subprocess.run(["docker", "manifest", "inspect", "-v", ref],
                             capture_output=True, text=True, timeout=120)
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout)
        if isinstance(data, list):
            data = data[0]
        return data.get("Descriptor", {}).get("digest")
    except Exception:
        return None


def heal_dockerfile(df: Path) -> tuple[bool, str]:
    text = df.read_text(encoding="utf-8")
    changed = False
    for ref in unpinned_bases(df):
        digest = resolve_digest(ref)
        if not digest:
            return False, f"could not resolve {ref} (needs network + docker login)"
        text = re.sub(rf"(^\s*FROM\s+){re.escape(ref)}(\s|$)",
                      rf"\g<1>{ref}@{digest}\g<2>", text, flags=re.IGNORECASE | re.MULTILINE)
        changed = True
    if changed:
        df.write_text(text, encoding="utf-8")
    return changed, "pinned" if changed else "nothing to pin"


def heal_requirements(rf: Path) -> tuple[bool, str]:
    """Freeze the ranges into a hash-pinned lock AND make the build actually use it.

    Writing a lockfile the Dockerfile never installs from is decoration, not remediation —
    the image would still resolve `fastapi>=0.110` at build time while a pinned lock sat
    unused beside it, looking like the problem was solved. So the Dockerfile is rewritten
    to COPY and `--require-hashes` install the lock. Verify the artifact, not the command.
    """
    lock = rf.with_name("requirements.lock")
    # Run from the app directory with relative paths so the generated header is portable
    # rather than embedding whatever absolute path this happened to be healed from.
    out = subprocess.run(
        ["uv", "pip", "compile", rf.name, "--generate-hashes", "-o", lock.name, "-q"],
        capture_output=True, text=True, timeout=600, cwd=rf.parent)
    if out.returncode != 0:
        return False, f"uv pip compile failed: {out.stderr.strip()[:200]}"

    df = rf.parent / "Dockerfile"
    if not df.exists():
        return True, f"wrote {lock.relative_to(ROOT)} (no image is built here; the lock is the pin)"
    text = df.read_text(encoding="utf-8")
    before = text

    # Path-agnostic: COPY and RUN may reference the file bare or fully qualified
    # (`COPY apps/x/requirements.txt /app/requirements.txt` + `pip install -r /app/requirements.txt`),
    # so rewrite the filename wherever it appears rather than matching one spelling.
    text = text.replace("requirements.txt", "requirements.lock")
    # A COPY whose DESTINATION names the file explicitly must name the LOCK too. Renaming only
    # the source produces `COPY requirements.lock ./requirements.txt` followed by
    # `pip install -r requirements.lock` — an install of a path that was never created. This
    # broke cloud-twin and identity-twin, and only surfaced in a real image build.
    text = re.sub(r"^(COPY\s+\S*requirements\.lock\s+\S*)requirements\.txt\s*$",
                  r"\1requirements.lock", text, flags=re.MULTILINE)
    # --require-hashes makes pip refuse any wheel whose hash is not declared, so a tampered or
    # substituted package fails the build instead of shipping. Add it to whichever pip install
    # consumes the lock, and drop the unpinned `--upgrade pip` that would run before it.
    text = re.sub(r"pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r ",
                  "pip install --no-cache-dir --require-hashes -r ", text)
    if "--require-hashes" not in text:
        text = re.sub(r"(pip install(?:(?!--require-hashes)[^\n])*?) -r (\S*requirements\.lock)",
                      r"\1 --require-hashes -r \2", text)

    if text == before or "--require-hashes" not in text:
        # A lock the build never reads is WORSE than no lock: it looks like the problem is
        # solved. Remove it and fail loudly rather than leaving a decorative artifact behind.
        lock.unlink(missing_ok=True)
        return False, ("could not rewire the Dockerfile to consume the lock — lock removed rather "
                       "than left inert; this Dockerfile's install line needs a look")
    df.write_text(text, encoding="utf-8")
    return True, f"wrote {lock.relative_to(ROOT)} + rewired Dockerfile to --require-hashes"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--heal", nargs="*", metavar="APP",
                    help="Resolve and WRITE the pins for the named apps (or all if none given).")
    args = ap.parse_args()

    ratchet = load_ratchet()
    r_base = ratchet.get("unpinned_base_images", {})
    r_reqs = ratchet.get("unpinned_requirements", {})

    if args.heal is not None:
        targets = set(args.heal)
        healed: dict[str, str] = {}
        for df in dockerfiles():
            app = df.parent.name
            if targets and app not in targets:
                continue
            if unpinned_bases(df):
                ok, msg = heal_dockerfile(df)
                healed[f"{app}/Dockerfile"] = msg
        for rf in requirement_files():
            app = rf.parent.name
            if targets and app not in targets:
                continue
            if unpinned_requirements(rf):
                ok, msg = heal_requirements(rf)
                healed[f"{app}/requirements.txt"] = msg
        print(json.dumps({"healed": healed}, indent=2, sort_keys=True))
        return 0

    failures: list[str] = []
    deferred = 0
    checks: dict[str, bool] = {}

    for df in dockerfiles():
        rel = str(df.relative_to(ROOT))
        bad = unpinned_bases(df)
        if bad and rel not in r_base:
            failures.append(f"{rel}: base image(s) not digest-pinned: {bad} — a tag is a mutable "
                            f"pointer, so this build is not reproducible")
        elif bad:
            deferred += 1
        elif rel in r_base:
            failures.append(f"{rel}: now digest-pinned but still in the ratchet — remove it. "
                            f"The ratchet only shrinks, or a fixed violation silently re-permits itself")
        else:
            checks[f"base-pinned:{rel}"] = True

        unreachable = lock_install_is_reachable(df)
        if unreachable:
            failures.append(f"{rel}: {unreachable} — the build would fail at pip install")
        else:
            checks[f"lock-reachable:{rel}"] = True

    for rf in requirement_files():
        rel = str(rf.relative_to(ROOT))
        bad = unpinned_requirements(rf)
        if bad and rel not in r_reqs:
            failures.append(f"{rel}: unpinned requirement(s) {bad[:3]}{'…' if len(bad) > 3 else ''} "
                            f"— a range defers the decision to whoever happens to build")
        elif bad:
            deferred += 1
        elif rel in r_reqs:
            failures.append(f"{rel}: now fully pinned but still in the ratchet — remove it")
        else:
            checks[f"reqs-pinned:{rel}"] = True

    for m in failures:
        print(f"FAIL: {m}", file=sys.stderr)
    ok = not failures
    print(json.dumps({
        "ok": ok,
        "dockerfiles": len(dockerfiles()),
        "requirementFiles": len(requirement_files()),
        "deferredByRatchet": deferred,
        "conformant": len(checks),
        "newViolations": len(failures),
    }, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
