#!/usr/bin/env bash
#
# Install a pinned, checksum-verified chart-releaser (`cr`) without using a
# third-party action.
#
# `helm/chart-releaser-action` cannot run in this repo. Actions here are
# restricted to `allowed_actions: selected` -- github-owned plus
# verified-Marketplace plus an explicit pattern allowlist (dtolnay/*,
# Swatinem/*, oven-sh/*, tauri-apps/*). chart-releaser-action *is* on the
# Marketplace (https://github.com/marketplace/actions/helm-chart-releaser
# returns 200), which makes this one easy to misdiagnose -- but its publisher
# `helm` carries no verified-creator badge, so `verified_allowed` does not
# cover it and it matches no pattern. Every run of helm-release.yml since the
# workflow was created is a `startup_failure` (17/17, 2026-06-23 -> 2026-07-29):
# the run is rejected before any job starts, so there are no logs to read.
#
# Downloading the release archive and checking it against a committed sha256 is
# strictly stronger than the action was: the checksum is reviewed in-tree, and
# no third-party code runs with access to the workflow token.
#
# Bumping CR_VERSION requires adding its checksum below. An unknown version is a
# hard error rather than an unverified download.

set -euo pipefail

CR_VERSION="${CR_VERSION:-1.8.1}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) GOARCH=amd64 ;;
  aarch64|arm64) GOARCH=arm64 ;;
  *) echo "::error::unsupported architecture ${ARCH}" >&2; exit 1 ;;
esac

# sha256 of chart-releaser_<version>_linux_<arch>.tar.gz, from the upstream
# checksums.txt attached to the release.
case "${CR_VERSION}_${GOARCH}" in
  1.8.1_amd64) SHA256=834046b27b00cd6ba451326875c1937d4f2b671063c2053e031434ade73002b5 ;;
  1.8.1_arm64) SHA256=03811896f65f73faffa63aa24f54ac4fed73e088418d0582723917b69c2a280b ;;
  *)
    echo "::error title=unpinned chart-releaser::no committed sha256 for chart-releaser ${CR_VERSION} ${GOARCH}." >&2
    echo "Add it from https://github.com/helm/chart-releaser/releases/download/v${CR_VERSION}/checksums.txt before bumping." >&2
    exit 1
    ;;
esac

TGZ="chart-releaser_${CR_VERSION}_linux_${GOARCH}.tar.gz"
URL="https://github.com/helm/chart-releaser/releases/download/v${CR_VERSION}/${TGZ}"
DEST="${CR_INSTALL_DIR:-/usr/local/bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading ${URL}"
curl -fsSL --retry 3 --retry-delay 2 -o "${TMP}/${TGZ}" "$URL"

echo "${SHA256}  ${TMP}/${TGZ}" | sha256sum -c -

tar -xzf "${TMP}/${TGZ}" -C "$TMP" cr
install -m 0755 "${TMP}/cr" "${DEST}/cr"

# Invoke by path, not via PATH, so this reports the binary just installed rather
# than some other cr that happens to be earlier in PATH.
"${DEST}/cr" version
