#!/usr/bin/env node
/**
 * Engine version guard for hellgraph-service.
 *
 * ── Why this exists (root cause, 2026-07) ────────────────────────────────────────────
 * The product silently shipped a STALE, forked engine: the vendored tarball was 0.4.6,
 * cut from a long-lived `feat/sparql-1.1` branch, while the engine's `main` had advanced
 * to 0.4.21 — 15 releases of work (the scale thesis + GDS / ANN / GraphRAG / retrieval
 * parity) that never reached production. The OLD guard only asserted the dep used a
 * `github:…#vX.Y.Z` tag ref — a format the project had already dropped for the sovereign
 * vendored-tarball model — so it failed-and-got-ignored and never checked the real thing:
 * IS THE SHIPPED ENGINE THE ONE WE INTEND, AND IS IT CURRENT?
 *
 * ── What it enforces now (for the vendored-tarball model) ────────────────────────────
 *   1. the dep resolves to a concrete version  (file:…-X.Y.Z.tgz  OR  …#vX.Y.Z tag)
 *   2. the vendored tarball EXISTS and its INTERNAL package.json version === the version
 *      in BOTH the filename and the dependency ref  (no mislabeled / missing tarball —
 *      this is the "two different 0.4.6s" confusion, caught)
 *   3. the vendored version is >= MIN_ENGINE, the estate's agreed floor — shipping older
 *      fails the build  (the stale-engine regression, caught)
 *   4. best-effort: if the engine repo is reachable, warn loudly when a newer release is
 *      tagged than what we vendor (a re-vendor is overdue). Non-fatal so CI never flakes.
 *
 * Engine consumers (this service + Noetica) MUST track the same release. When you cut a
 * new engine release: bump MIN_ENGINE **and** vendor the matching tarball in the SAME
 * change. The floor and the tarball move together or the build goes red.
 */
import { readFileSync, existsSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// ── the estate's floor: the OLDEST engine we are allowed to ship. Bump on every release. ──
const MIN_ENGINE = '0.4.26'
const ENGINE_REMOTE = process.env.HELLGRAPH_ENGINE_REMOTE || 'https://github.com/SocioProphet/hellgraph.git'

const die = (m) => { console.error(`✗ ${m}`); process.exit(1) }
const parse = (v) => v.split('.').map(Number)
const cmp = (a, b) => { const pa = parse(a), pb = parse(b); for (let i = 0; i < 3; i++) if (pa[i] !== pb[i]) return pa[i] - pb[i]; return 0 }

const here = dirname(fileURLToPath(import.meta.url))
const svcRoot = join(here, '..')
const pkg = JSON.parse(readFileSync(join(svcRoot, 'package.json'), 'utf8'))
const spec = pkg.dependencies?.['@socioprophet/hellgraph']
if (!spec) die('@socioprophet/hellgraph not in dependencies')

// 1) extract the pinned version from either supported form
let version, tgzPath, m
if ((m = spec.match(/^file:(.*socioprophet-hellgraph-(\d+\.\d+\.\d+)\.tgz)$/))) { tgzPath = join(svcRoot, m[1]); version = m[2] }
else if ((m = spec.match(/#v?(\d+\.\d+\.\d+)$/))) { version = m[1] }
else die(`engine dep must pin a concrete version — file:vendor/socioprophet-hellgraph-X.Y.Z.tgz or …#vX.Y.Z (got "${spec}")`)

// 2) vendored-tarball integrity: exists + INTERNAL version === filename/ref version
if (tgzPath) {
  if (!existsSync(tgzPath)) die(`vendored engine tarball missing: ${tgzPath}`)
  let internalVersion
  try { internalVersion = JSON.parse(execFileSync('tar', ['xzOf', tgzPath, 'package/package.json'], { encoding: 'utf8' })).version }
  catch { die(`cannot read package.json inside ${tgzPath}`) }
  if (internalVersion !== version)
    die(`tarball MISLABELED: ref/filename says ${version} but the package.json inside says ${internalVersion} (${tgzPath})`)
}

// 3) freshness floor — never ship older than the estate agreed to
if (cmp(version, MIN_ENGINE) < 0)
  die(`engine ${version} is BELOW the floor ${MIN_ENGINE} — re-vendor a current build. This is exactly the stale-engine regression this guard exists to stop.`)

// 4) best-effort: is a newer engine release tagged than what we vendor?
try {
  const out = execFileSync('git', ['ls-remote', '--tags', '--refs', ENGINE_REMOTE], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 5000 })
  const latest = out.split('\n').map((l) => (l.match(/refs\/tags\/v?(\d+\.\d+\.\d+)$/) || [])[1]).filter(Boolean).sort(cmp).pop()
  if (latest && cmp(latest, version) > 0)
    console.warn(`⚠ engine repo has v${latest} tagged but we vendor ${version} — a re-vendor is overdue.`)
} catch { /* offline / private / no git — the floor + integrity checks above still hold */ }

console.log(`✓ hellgraph-service ships engine ${version} (floor ${MIN_ENGINE}; keep in sync with Noetica)`)
