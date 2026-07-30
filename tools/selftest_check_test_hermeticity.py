#!/usr/bin/env python3
"""Prove-it-fires for check_test_hermeticity.py.

Teeth in both directions: raw writes under real $HOME must go RED; the
env-redirectable idiom, tmp writes, and reads under HOME must stay GREEN (the
negative controls that catch a scanner which flags everything, or nothing).

Run directly:  python3 tools/selftest_check_test_hermeticity.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCANNER = HERE / "check_test_hermeticity.py"

# Each of these is a genuine, distinct way to write under the real HOME.
BAD_FILES = {
    "b_open.py": (
        "from pathlib import Path\n"
        "def go():\n"
        "    open(Path.home() / '.noetica' / 'x', 'w').write('hi')\n"
    ),
    "b_sqlite.py": (
        "import sqlite3\n"
        "from pathlib import Path\n"
        "_DB = Path.home() / '.noetica' / 'hellgraph.db'\n"
        "def go():\n"
        "    return sqlite3.connect(str(_DB))\n"
    ),
    "b_writetext.py": (
        "from pathlib import Path\n"
        "def go():\n"
        "    (Path.home() / '.config' / 'f').write_text('x')\n"
    ),
    "b_makedirs.py": (
        "import os\n"
        "def go():\n"
        "    os.makedirs(os.path.expanduser('~/.noetica/z'), exist_ok=True)\n"
    ),
    "b_environ.py": (
        "import os\n"
        "def go():\n"
        "    open(os.environ['HOME'] + '/.secret', 'a').write('x')\n"
    ),
}

# Each of these MUST NOT be flagged.
GOOD_FILES = {
    "g_env_redirect.py": (
        "import os\n"
        "from pathlib import Path\n"
        "DB = Path(os.environ.get('APP_DB', str(Path.home() / '.noetica' / 'x.db')))\n"
        "def go():\n"
        "    open(DB, 'w').write('ok')\n"           # redirectable via APP_DB -> hermetic
    ),
    "g_tmp.py": (
        "import tempfile, os\n"
        "def go():\n"
        "    d = tempfile.mkdtemp()\n"
        "    open(os.path.join(d, 'x'), 'w').write('ok')\n"
    ),
    "g_read_only.py": (
        "from pathlib import Path\n"
        "def go():\n"
        "    return open(Path.home() / '.gitconfig').read()\n"  # READ under HOME is fine
    ),
    "g_getenv_default.py": (
        "import os\n"
        "from pathlib import Path\n"
        "def go():\n"
        "    p = os.getenv('OUT_DIR', str(Path.home() / '.noetica'))\n"
        "    (Path(p) / 'f').write_text('ok')\n"     # OUT_DIR redirect -> hermetic
    ),
}


def run(base: Path, scan: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCANNER), "--base", str(base), "--scan", scan],
        capture_output=True, text=True,
    )


def write(d: Path, files: dict[str, str]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")


def main() -> int:
    results: list[bool] = []
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        write(base / "bad", BAD_FILES)
        write(base / "good", GOOD_FILES)

        # KNOWN POSITIVE: bad dir -> RED, and every planted file must be named.
        cp_bad = run(base, "bad")
        named = all(fn.split(".")[0] in cp_bad.stdout for fn in BAD_FILES)
        bad_ok = cp_bad.returncode == 1 and named
        print(f"[{'PASS' if bad_ok else 'FAIL'}] bad dir -> RED and all {len(BAD_FILES)} patterns flagged "
              f"(rc={cp_bad.returncode}, all_named={named})")
        if not bad_ok:
            print(cp_bad.stdout, cp_bad.stderr)
        results.append(bad_ok)

        # KNOWN NEGATIVE: good dir -> GREEN (no false positives).
        cp_good = run(base, "good")
        good_ok = cp_good.returncode == 0
        print(f"[{'PASS' if good_ok else 'FAIL'}] good dir -> GREEN (redirectable/tmp/read) rc={cp_good.returncode}")
        if not good_ok:
            print(cp_good.stdout, cp_good.stderr)
        results.append(good_ok)

        # Per-pattern negative controls: confirm each good file individually clears.
        for fn in GOOD_FILES:
            one = base / "one"
            write(one, {fn: GOOD_FILES[fn]})
            cp = run(base, "one")
            ok = cp.returncode == 0
            print(f"[{'PASS' if ok else 'FAIL'}]   negative control {fn} clean (rc={cp.returncode})")
            results.append(ok)
            for p in one.iterdir():
                p.unlink()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
