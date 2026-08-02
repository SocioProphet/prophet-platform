#!/usr/bin/env bash
#
# Install a pinned, checksum-verified OpenTofu without using a third-party action.
#
# `opentofu/setup-opentofu` cannot run in this repo. Actions here are restricted
# to `allowed_actions: selected` -- github-owned plus verified-Marketplace plus
# an explicit pattern allowlist (dtolnay/*, Swatinem/*, oven-sh/*, tauri-apps/*).
# setup-opentofu is not on the Marketplace at all
# (https://github.com/marketplace/actions/setup-opentofu returns 404), so it is
# none of those. Every scheduled run of infra-drift-detect.yml since it was
# created on 2026-07-03 is a `startup_failure` (26/26), and tofu-plan.yml went
# the same way from 2026-06-23 onward after succeeding earlier in June.
#
# Downloading the release archive and checking it against a committed sha256 is
# strictly stronger than the action was: the checksum is reviewed in-tree, and
# no third-party code runs with access to the workflow token.
#
# Bumping TOFU_VERSION requires adding its checksum below. An unknown version is
# a hard error rather than an unverified download.

set -euo pipefail

TOFU_VERSION="${TOFU_VERSION:-1.8.3}"
ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) GOARCH=amd64 ;;
  aarch64|arm64) GOARCH=arm64 ;;
  *) echo "::error::unsupported architecture ${ARCH}" >&2; exit 1 ;;
esac

# sha256 of tofu_<version>_linux_<arch>.zip, from the upstream SHA256SUMS.
case "${TOFU_VERSION}_${GOARCH}" in
  1.8.3_amd64) SHA256=dc44b452a407648a40900eea5ceca2dd586dd084ae085863dba997331dcf8225 ;;
  1.8.3_arm64) SHA256=c3ea55a86aaf22729be63371176fdefa40ae9632a6b620c64b98d7fb3a13205e ;;
  *)
    echo "::error title=unpinned OpenTofu::no committed sha256 for OpenTofu ${TOFU_VERSION} ${GOARCH}." >&2
    echo "Add it from https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_SHA256SUMS before bumping." >&2
    exit 1
    ;;
esac

ZIP="tofu_${TOFU_VERSION}_linux_${GOARCH}.zip"
URL="https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/${ZIP}"
DEST="${TOFU_INSTALL_DIR:-/usr/local/bin}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading ${URL}"
curl -fsSL --retry 3 --retry-delay 2 -o "${TMP}/${ZIP}" "$URL"

echo "${SHA256}  ${TMP}/${ZIP}" | sha256sum -c -

unzip -q -o "${TMP}/${ZIP}" tofu -d "$TMP"
install -m 0755 "${TMP}/tofu" "${DEST}/tofu"

# Invoke by path, not via PATH, so this reports the binary just installed rather
# than some other tofu that happens to be earlier in PATH.
"${DEST}/tofu" version
