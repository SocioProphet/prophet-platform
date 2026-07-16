#!/usr/bin/env bash
# Phase 2 ("migrate the runner off Google") stays real only if install-act-runner.sh
# never grows a Google dependency. Promises rot; a test doesn't. This is that test.
#
# It deliberately ignores comments and the closing help text — prose saying "GCE"
# is documentation, not a dependency. Only executable code counts.
set -euo pipefail
cd "$(dirname "$0")"
python3 - <<'PY'
import re, sys
src = open('install-act-runner.sh').read()
code = re.sub(r'(?m)^\s*#.*$', '', src)              # strip comments
code = re.sub(r'cat <<EOF.*?\nEOF', '', code, flags=re.S)  # strip help text
bad = re.compile(r'googleapis|metadata\.google|\bgcloud\b|workload.identity|169\.254\.169\.254', re.I)
hits = [l.strip() for l in code.splitlines() if bad.search(l)]
if hits:
    print("FAIL: install-act-runner.sh grew a Google dependency — Phase 2 would become a rewrite:")
    for h in hits: print("  •", h)
    sys.exit(1)
print("OK: install-act-runner.sh has no Google dependency in executable code —")
print("    Phase 2 (anchor box) stays a re-run, not a rewrite.")
PY
