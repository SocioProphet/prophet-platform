/**
 * The S3 seam, both sides:
 *  - contract test — the engine's S3ObjectBackend + CanonicalObjectStore over a FAKE
 *    S3Client (bytes content-addressed, roundtrip, integrity verify);
 *  - adapter unit test — MinioS3Client over a stubbed minio client (stream reads,
 *    NoSuchKey → undefined, real errors propagate). No network anywhere.
 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Readable } from 'node:stream'
import { CanonicalObjectStore, S3ObjectBackend, type S3Client } from '@socioprophet/hellgraph'
import { MinioS3Client, parseEndpoint, type MinioLike } from './minio-store.js'

class FakeS3 implements S3Client {
  readonly objects = new Map<string, Buffer>()
  async putObject(bucket: string, key: string, body: Buffer): Promise<void> {
    this.objects.set(`${bucket}/${key}`, Buffer.from(body))
  }
  async getObject(bucket: string, key: string): Promise<Buffer | undefined> {
    const b = this.objects.get(`${bucket}/${key}`)
    return b ? Buffer.from(b) : undefined
  }
}

test('engine S3ObjectBackend contract: content-addressed put/get through CanonicalObjectStore', async () => {
  const s3 = new FakeS3()
  const store = new CanonicalObjectStore(new S3ObjectBackend(s3, 'warden-test', 'objects/'))
  const entry = await store.ingest('doc-1', 'sovereign bytes', { mime: 'text/plain', residency: 'sovereign' })

  // the bytes landed under `objects/<contentHash>` in the named bucket — dedup by construction
  assert.ok(s3.objects.has(`warden-test/objects/${entry.contentHash}`))

  const got = await store.get('doc-1')
  assert.equal(got!.content, 'sovereign bytes')

  // codex integrity verify over the stored bytes: INTACT
  const syn = await store.verify('doc-1')
  assert.equal(syn.class, 'INTACT')
  assert.equal(syn.exact, true)

  // same content, second object → same key, no second blob
  const before = s3.objects.size
  await store.ingest('doc-2', 'sovereign bytes', { mime: 'text/plain', residency: 'sovereign' })
  assert.equal(s3.objects.size, before)
})

function stubMinio(blobs: Map<string, Buffer>, opts?: { failGet?: string }): MinioLike {
  return {
    async putObject(bucket, key, body) { blobs.set(`${bucket}/${key}`, Buffer.from(body)) },
    async getObject(bucket, key) {
      if (opts?.failGet === key) throw Object.assign(new Error('boom'), { code: 'InternalError' })
      const b = blobs.get(`${bucket}/${key}`)
      if (!b) throw Object.assign(new Error(`no such key ${key}`), { code: 'NoSuchKey' })
      return Readable.from([b.subarray(0, 3), b.subarray(3)]) // multi-chunk stream on purpose
    },
    async bucketExists() { return true },
    async makeBucket() {},
  }
}

test('MinioS3Client adapter: buffers streamed reads, absent key → undefined, real errors propagate', async () => {
  const blobs = new Map<string, Buffer>()
  const client = new MinioS3Client(stubMinio(blobs, { failGet: 'poison' }))
  await client.putObject('b', 'k1', Buffer.from('hello minio'))
  assert.equal((await client.getObject('b', 'k1'))!.toString('utf8'), 'hello minio')
  assert.equal(await client.getObject('b', 'missing'), undefined)
  await assert.rejects(client.getObject('b', 'poison'), /boom/) // outages must not read as "absent"
})

test('parseEndpoint accepts host, host:port, and full URLs', () => {
  assert.deepEqual(parseEndpoint('workspace-minio:9000'), { endPoint: 'workspace-minio', port: 9000, useSSL: false })
  assert.deepEqual(parseEndpoint('workspace-minio'), { endPoint: 'workspace-minio', port: 9000, useSSL: false })
  assert.deepEqual(parseEndpoint('http://minio.local:9100'), { endPoint: 'minio.local', port: 9100, useSSL: false })
  assert.deepEqual(parseEndpoint('https://s3.example.com'), { endPoint: 's3.example.com', port: 443, useSSL: true })
})
