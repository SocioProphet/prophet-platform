/**
 * Run sealing on THE estate receipt spine — compute-gateway POST /v1/compute,
 * kind=governance (added beside `materialize`; same shape, same chain, same Ed25519
 * attestation — never a parallel receipt lineage).
 *
 * Degradation is honest, not silent: a gateway failure returns {ok:false}; the caller
 * counts it (healthz unsealedRuns) while the local hash-chained audit keeps chaining —
 * the run's evidence exists either way, only the spine attestation is missing.
 */
import type { RunReport } from './warden.js'

export interface SealResult { ok: boolean, receiptId?: string, error?: string }

export interface Sealer { seal(report: RunReport): Promise<SealResult> }

export class NoopSealer implements Sealer {
  async seal(): Promise<SealResult> { return { ok: false, error: 'sealing disabled (no GATEWAY_TOKEN)' } }
}

export class GatewaySealer implements Sealer {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    private readonly project = 'default',
    private readonly timeoutMs = 15_000,
  ) {}

  async seal(report: RunReport): Promise<SealResult> {
    const body = {
      kind: 'governance',
      project: this.project,
      actor: 'lifecycle-warden',
      spec: {
        service: 'lifecycle-warden',
        run_id: report.runId,
        dry_run: report.dryRun,
        objects_scanned: report.objectsScanned,
        due_count: report.dueCount,
        applied_count: report.applied.length,
        planned_count: report.planned.length,
        gc_count: report.gcCount,
        audit_seq: report.auditHead?.seq ?? -1,
        audit_head: report.auditHead?.hash ?? 'empty',
      },
    }
    try {
      const r = await fetch(`${this.baseUrl.replace(/\/$/, '')}/v1/compute`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', authorization: `Bearer ${this.token}` },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.timeoutMs),
      })
      if (!r.ok) return { ok: false, error: `compute-gateway ${r.status}: ${(await r.text()).slice(0, 300)}` }
      const result = (await r.json()) as { status?: string, receipt?: { id?: string } | null }
      if (result.status !== 'ok' || !result.receipt?.id) {
        return { ok: false, error: `governance receipt refused: ${JSON.stringify(result).slice(0, 300)}` }
      }
      return { ok: true, receiptId: result.receipt.id }
    } catch (err) {
      return { ok: false, error: `compute-gateway unreachable: ${(err as Error).message}` }
    }
  }
}
