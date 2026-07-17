import { test } from 'node:test'
import assert from 'node:assert/strict'
import { synthesize, synthesisEnabled } from './synthesize.js'
import type { SearchResult } from './gateway.js'

const RESULTS: SearchResult[] = [
  { title: 'Sovereign AI explained', url: 'https://a.example/1', snippet: 'Sovereign AI is nation/org-controlled AI.', source: 'web', engine: 'bing' },
  { title: 'Commons note', url: 'noetica://open-chat/x', snippet: 'The sovereign commons is opt-in and redacted.', source: 'commons', engine: 'noetica-commons' },
]
const ENV = ['SEARCH_LLM_URL', 'SEARCH_LLM_MODEL', 'SEARCH_LLM_KEY']
function clearEnv() { for (const k of ENV) delete process.env[k] }

test('no LLM configured → citations returned, no answer (degrade to results)', async () => {
  clearEnv()
  assert.equal(synthesisEnabled(), false)
  const s = await synthesize('what is sovereign ai', RESULTS)
  assert.equal(s.synthesized, false)
  assert.equal(s.citations.length, 2)
  assert.equal(s.citations[0]!.n, 1)
  assert.equal(s.answer, '')
})

test('configured LLM → grounded cited answer', async () => {
  process.env.SEARCH_LLM_URL = 'http://sovereign-llm:8000/v1'
  process.env.SEARCH_LLM_MODEL = 'prophet-7b'
  let body: any
  const fake = (async (_u: string, init: RequestInit) => {
    body = JSON.parse(init.body as string)
    return new Response(JSON.stringify({ choices: [{ message: { content: 'Sovereign AI is org-controlled AI [1], and the commons is opt-in [2].' } }] }), { headers: { 'content-type': 'application/json' } })
  }) as unknown as typeof fetch
  const s = await synthesize('what is sovereign ai', RESULTS, fake)
  assert.equal(s.synthesized, true)
  assert.match(s.answer, /\[1\]/)
  assert.equal(body.model, 'prophet-7b')
  assert.match(body.messages[0].content, /ONLY the numbered sources/)  // grounded prompt
  clearEnv()
})

test('LLM error → fail-open to results-only', async () => {
  process.env.SEARCH_LLM_URL = 'http://x/v1'; process.env.SEARCH_LLM_MODEL = 'm'
  const errFetch = (async () => new Response('nope', { status: 500 })) as unknown as typeof fetch
  const s = await synthesize('q', RESULTS, errFetch)
  assert.equal(s.synthesized, false)
  assert.equal(s.citations.length, 2)
  clearEnv()
})
