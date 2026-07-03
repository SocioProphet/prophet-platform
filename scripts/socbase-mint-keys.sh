#!/usr/bin/env bash
# Mint the Socbase (self-hosted Supabase) demo-style ANON_KEY / SERVICE_ROLE_KEY
# HS256 JWTs from a JWT secret — no external deps, pure Node `crypto`.
# Usage: ./scripts/socbase-mint-keys.sh [jwt-secret]
#   - jwt-secret omitted → generates a fresh one (openssl rand -base64 32) and prints it too.
# These keys never expire by default (Supabase's own self-host demo keys use
# a far-future exp) — rotate by re-running with a new secret and redeploying.
set -euo pipefail

SECRET="${1:-$(openssl rand -base64 32)}"

node -e '
const crypto = require("crypto");
const secret = process.argv[1];

function b64url(buf) {
  return Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function sign(role) {
  const header = { alg: "HS256", typ: "JWT" };
  const payload = { role, iss: "socbase", iat: Math.floor(Date.now() / 1000), exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 365 * 10 };
  const signingInput = b64url(JSON.stringify(header)) + "." + b64url(JSON.stringify(payload));
  const sig = crypto.createHmac("sha256", secret).update(signingInput).digest();
  return signingInput + "." + b64url(sig);
}

console.log("JWT_SECRET=" + secret);
console.log("ANON_KEY=" + sign("anon"));
console.log("SERVICE_ROLE_KEY=" + sign("service_role"));
' "$SECRET"

echo
echo "Wire these into:"
echo "  - k8s Secret 'socbase-jwt' key 'secret'                → JWT_SECRET"
echo "  - server/.env: SUPABASE_SERVICE_ROLE_KEY                → SERVICE_ROLE_KEY"
echo "  - app-vue/public/socbase-config.js: anonKey             → ANON_KEY"
echo "  - server/.env + socbase-config.js: SUPABASE_URL / url   → https://<gatewayHostname>"
