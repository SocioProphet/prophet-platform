/**
 * MinIO wiring — the first real implementation behind the engine's BYOS seams.
 *
 * object-store.ts shipped `S3ObjectBackend` with an injectable `S3Client` interface and
 * ZERO implementations (the blueprint-audit finding). `MinioS3Client` is that
 * implementation, over the in-cluster MinIO (Service `workspace-minio`, namespace
 * socioprophet, S3 port 9000 — infra/k8s/workspace-minio). The same connection also
 * backs `MinioBlobStore`, the audit-chunk + warden-state persistence (audit.ts BlobStore).
 *
 * Credentials come from the `minio-credentials` Secret (keys access-key/secret-key —
 * the same Secret MinIO itself and zot's S3 backend use), injected via the chart's
 * secretEnv. No PATs, nothing static in git.
 */
import type { Readable } from 'node:stream'
import { Client as MinioClient } from 'minio'

/** The engine's injectable S3 seam (object-store.ts). Kept structural — no engine import needed. */
export interface EngineS3Client {
  putObject(bucket: string, key: string, body: Buffer): Promise<void>
  getObject(bucket: string, key: string): Promise<Buffer | undefined>
}

/** The slice of minio.Client we use — injectable so unit tests need no network. */
export interface MinioLike {
  putObject(bucket: string, key: string, body: Buffer): Promise<unknown>
  getObject(bucket: string, key: string): Promise<Readable>
  bucketExists(bucket: string): Promise<boolean>
  makeBucket(bucket: string): Promise<void>
}

export interface MinioConfig {
  endPoint: string
  port: number
  useSSL: boolean
  accessKey: string
  secretKey: string
  bucket: string
}

/** Parse MINIO_ENDPOINT: `host`, `host:port`, or `http(s)://host[:port]`. */
export function parseEndpoint(raw: string): { endPoint: string, port: number, useSSL: boolean } {
  const url = /^[a-z]+:\/\//i.test(raw) ? new URL(raw) : new URL(`http://${raw}`)
  const useSSL = url.protocol === 'https:'
  const port = url.port ? Number(url.port) : (useSSL ? 443 : 9000)
  return { endPoint: url.hostname, port, useSSL }
}

async function readAll(stream: Readable): Promise<Buffer> {
  const parts: Buffer[] = []
  for await (const c of stream) parts.push(Buffer.isBuffer(c) ? c : Buffer.from(c))
  return Buffer.concat(parts)
}

function isNoSuchKey(err: unknown): boolean {
  const code = (err as { code?: string } | null)?.code
  return code === 'NoSuchKey' || code === 'NotFound'
}

/** The engine's S3Client, implemented — S3ObjectBackend(client, bucket) plugs straight in. */
export class MinioS3Client implements EngineS3Client {
  constructor(private readonly client: MinioLike) {}

  async putObject(bucket: string, key: string, body: Buffer): Promise<void> {
    await this.client.putObject(bucket, key, body)
  }

  async getObject(bucket: string, key: string): Promise<Buffer | undefined> {
    try {
      return await readAll(await this.client.getObject(bucket, key))
    } catch (err) {
      if (isNoSuchKey(err)) return undefined
      throw err
    }
  }
}

/** audit.ts BlobStore over one bucket — audit chunks + the governed-object registry. */
export class MinioBlobStore {
  constructor(private readonly client: MinioLike, private readonly bucket: string) {}

  async put(key: string, body: Buffer): Promise<void> {
    await this.client.putObject(this.bucket, key, body)
  }

  async get(key: string): Promise<Buffer | undefined> {
    try {
      return await readAll(await this.client.getObject(this.bucket, key))
    } catch (err) {
      if (isNoSuchKey(err)) return undefined
      throw err
    }
  }
}

export function connect(cfg: MinioConfig): MinioLike {
  return new MinioClient({
    endPoint: cfg.endPoint,
    port: cfg.port,
    useSSL: cfg.useSSL,
    accessKey: cfg.accessKey,
    secretKey: cfg.secretKey,
  }) as unknown as MinioLike
}

export async function ensureBucket(client: MinioLike, bucket: string): Promise<void> {
  if (!(await client.bucketExists(bucket))) await client.makeBucket(bucket)
}
