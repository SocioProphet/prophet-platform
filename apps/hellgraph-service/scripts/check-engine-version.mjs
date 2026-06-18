#!/usr/bin/env node
/**
 * Engine pin guard for hellgraph-service.
 *
 * This service shares the @socioprophet/hellgraph engine with Noetica. They must
 * track the SAME tagged release or the HTTP service and the app diverge in graph
 * semantics. This asserts the dependency is pinned to a release tag (not a floating
 * ref) and prints it; cross-repo parity with Noetica is documented in the message.
 *
 * Canonical version lives in Noetica (scripts/check-engine-version.mjs). When you
 * bump one, bump both.
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const pkg = JSON.parse(readFileSync(join(here, '..', 'package.json'), 'utf8'))
const spec = pkg.dependencies?.['@socioprophet/hellgraph']

if (!spec) { console.error('✗ @socioprophet/hellgraph not in dependencies'); process.exit(1) }
const m = spec.match(/#(v\d+\.\d+\.\d+)$/)
if (!m) {
  console.error(`✗ engine must pin a release tag (got "${spec}") — use github:SocioProphet/hellgraph#vX.Y.Z`)
  process.exit(1)
}
console.log(`✓ hellgraph-service pins engine ${m[1]} (keep in sync with Noetica)`)
