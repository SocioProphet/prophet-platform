#!/usr/bin/env bash
# Proof that the mail-backup non-triviality gate fails a trivial (empty-maildir)
# archive and passes a real one.
#
# It does NOT re-implement the backup logic. It renders the SHIPPED manifest
# (kubectl kustomize), extracts the mail-backup container's command script and
# its env defaults verbatim, and runs THAT against two synthesized maildir
# fixtures. The only transformation is localizing the two mount paths
# (/maildata, /backup) to temp dirs so it can run unprivileged off-cluster; the
# tar invocation, the tar-tzf verify and the wc -c size gate are the real ones.
#
# Local-only (Actions are spend-capped). Requires: kubectl, python3, tar.
# Provides a sha256sum shim (-> shasum -a 256) so the receipt step runs on macOS.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BASE="$(cd "$HERE/../base" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# sha256sum shim for macOS (Linux/alpine already have it).
mkdir -p "$WORK/shim"
if ! command -v sha256sum >/dev/null 2>&1; then
  cat >"$WORK/shim/sha256sum" <<'EOF'
#!/bin/sh
exec shasum -a 256 "$@"
EOF
  chmod +x "$WORK/shim/sha256sum"
fi
export PATH="$WORK/shim:$PATH"

# --- extract the shipped script + env defaults from the rendered manifest ----
kubectl kustomize "$BASE" >"$WORK/rendered.yaml"
python3 - "$WORK/rendered.yaml" "$WORK/script.sh" "$WORK/env.sh" <<'PY'
import sys, yaml
rendered, script_out, env_out = sys.argv[1], sys.argv[2], sys.argv[3]
docs = list(yaml.safe_load_all(open(rendered)))
cj = [d for d in docs if d and d.get("kind") == "CronJob" and d["metadata"]["name"] == "mail-backup"][0]
c = cj["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
open(script_out, "w").write(c["command"][2])
with open(env_out, "w") as f:
    for e in c["env"]:
        f.write('export %s=%s\n' % (e["name"], e.get("value", "")))
PY

# Localize ONLY the mount paths. Logic (tar/verify/size-gate/receipt) untouched.
SRC="$WORK/src"; DST="$WORK/dst"
mkdir -p "$SRC" "$DST"
sed "s#/maildata#$SRC#g; s#/backup#$DST#g" "$WORK/script.sh" >"$WORK/script.local.sh"

run_backup() { ( set -a; . "$WORK/env.sh"; set +a; sh "$WORK/script.local.sh" ); }

pass=0; fail=0
ok()   { echo "  PASS: $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL: $1"; fail=$((fail+1)); }

# ---------------------------------------------------------------------------
echo "== fixture A: empty maildir (zero mail) =="
rm -rf "$SRC" "$DST"; mkdir -p "$SRC" "$DST"
# ext4 lost+found (proves the exclude) + the empty maildir skeleton dovecot lays
# down with NO messages. This is the live 'zero mail' state.
mkdir -p "$SRC/lost+found" "$SRC/example.com/alice/Maildir/cur" \
         "$SRC/example.com/alice/Maildir/new" "$SRC/example.com/alice/Maildir/tmp"
echo "orphan" >"$SRC/lost+found/#123"

# Show the archive size this state produces with the shipped tar invocation.
tar czf "$WORK/empty.tar.gz" -C "$SRC" --exclude=./lost+found . 2>/dev/null
EMPTY_BYTES=$(wc -c < "$WORK/empty.tar.gz" | tr -d ' ')
echo "  empty-maildir archive is ${EMPTY_BYTES} bytes (live-observed ~130)"
if [ "$EMPTY_BYTES" -lt 1024 ]; then ok "empty archive is trivially small (< 1024B floor)"; else bad "empty archive unexpectedly >= 1024B"; fi

set +e; out="$(run_backup 2>&1)"; rc=$?; set -e
echo "$out" | sed 's/^/    | /'
[ "$rc" -ne 0 ] && ok "job FAILED on empty maildir (exit $rc)" || bad "job passed on empty maildir (should fail)"
echo "$out" | grep -q "refusing to record a trivial backup" && ok "size gate emitted the refusal" || bad "no size-gate refusal in output"
ls "$DST"/mail-*.tar.gz >/dev/null 2>&1 && bad "trivial archive was left on disk" || ok "trivial archive was removed, not receipted"

# ---------------------------------------------------------------------------
echo "== fixture B: populated maildir (real mail) =="
rm -rf "$SRC" "$DST"; mkdir -p "$SRC" "$DST"
mkdir -p "$SRC/lost+found" "$SRC/example.com/alice/Maildir/cur"
echo "orphan" >"$SRC/lost+found/#123"
MSG="$SRC/example.com/alice/Maildir/cur/1706500000.M1P1.mail:2,S"
{
  echo "From: bob@example.com"
  echo "To: alice@example.com"
  echo "Subject: Q3 board pack"
  echo "Date: Tue, 29 Jul 2026 09:00:00 +0000"
  echo
  echo "Alice -- attaching the board pack. Regards, Bob"
  echo
  # High-entropy blob so the archive is non-trivial even after gzip (models an
  # attachment); guarantees it clears the 1024-byte floor.
  head -c 6144 /dev/urandom | base64
} >"$MSG"

set +e; out="$(run_backup 2>&1)"; rc=$?; set -e
echo "$out" | sed 's/^/    | /'
[ "$rc" -eq 0 ] && ok "job SUCCEEDED on populated maildir (exit 0)" || bad "job failed on real mail (should pass)"
ARCH="$(ls "$DST"/mail-*.tar.gz 2>/dev/null | head -n1 || true)"
if [ -n "$ARCH" ]; then
  ok "archive retained: $(basename "$ARCH")"
  B=$(wc -c < "$ARCH" | tr -d ' '); [ "$B" -ge 1024 ] && ok "real archive is ${B} bytes (>= 1024B floor)" || bad "real archive ${B}B under floor"
  if tar tzf "$ARCH" | grep -q "lost+found"; then bad "lost+found leaked into the archive"; else ok "lost+found excluded from archive"; fi
  tar tzf "$ARCH" | grep -q "alice/Maildir/cur" && ok "real mail present in archive" || bad "mail missing from archive"
else
  bad "no archive produced for populated maildir"
fi

echo
echo "RESULT: ${pass} passed, ${fail} failed"
[ "$fail" -eq 0 ]
