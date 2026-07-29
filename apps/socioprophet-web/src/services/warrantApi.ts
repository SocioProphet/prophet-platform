/**
 * Warrant surfaces API (W11).
 *
 * Two doors, in two very different states of readiness — and this module says which is
 * which rather than blurring them:
 *
 *   • verifyReceipt()   LIVE SHAPE. Calls the compute-gateway's real endpoint,
 *                       `GET /v1/engine-receipts/{receipt_id}/verify`, whose response is
 *                       passed through verbatim from `engine_receipts.py::verify_walk`.
 *                       It is unreachable from the cockpit today only because no
 *                       `/svc/gateway` proxy exists yet — so with no base configured the
 *                       call reports `unavailable`, never a fabricated pass.
 *
 *   • compileQuestion() FIXTURE-BACKED. The NLQ typed-plan compiler lives in the hellgraph
 *                       ENGINE (`ts/src/nlq.ts::compileQuestion`, v0.4.44+) and is not
 *                       exposed over HTTP by any service in this repo. Until it is, this
 *                       returns the fixture and stamps `mode: 'fixture'`. Every consumer
 *                       renders that stamp; nothing pretends the plan came off a live graph.
 */
import { resolveBase } from '../config/cockpitRuntime';
import {
  FIXTURE_COMPILATION,
  FIXTURE_SEAL_DEGRADED,
  FIXTURE_WALK_VALID,
} from '../data/warrantFixture';
import type {
  NlqCompilation,
  ReceiptVerifyWalk,
  ReceiptWalkStatus,
  SealOutcome,
} from '../features/warrant/types';

/**
 * No `/svc/gateway` proxy exists in vite.config.ts or the nginx config yet, so this is
 * deliberately declared WITHOUT a code fallback: unset means unavailable, which is the
 * truth, rather than a path that 404s and looks like a verification failure.
 */
const GATEWAY = resolveBase('gateway', 'VITE_GATEWAY_BASE');

export type WarrantLoadMode = 'live' | 'fixture' | 'unavailable';

export interface CompileResult {
  data: NlqCompilation | null;
  mode: WarrantLoadMode;
  /** The seal that rode with the compilation. */
  seal: SealOutcome;
  error?: string;
}

export interface VerifyResult {
  data: ReceiptVerifyWalk | null;
  mode: WarrantLoadMode;
  error?: string;
}

const WALK_STATUSES: ReceiptWalkStatus[] = ['ok', 'fail', 'skipped'];

/**
 * Validate the gateway's payload before trusting it. A verify walk that does not parse is
 * NOT a pass — it is an error, and gets reported as one. This is the same posture the
 * server takes: never let an unverifiable thing read as verified.
 */
function parseWalk(raw: unknown): ReceiptVerifyWalk | null {
  if (!raw || typeof raw !== 'object') return null;
  const o = raw as Record<string, unknown>;
  if (typeof o['valid'] !== 'boolean') return null;
  if (typeof o['receipt_id'] !== 'string' || typeof o['project'] !== 'string') return null;
  if (!Array.isArray(o['steps'])) return null;
  const steps = o['steps'].map((s) => {
    const st = (s ?? {}) as Record<string, unknown>;
    const status = st['status'];
    return {
      step: typeof st['step'] === 'string' ? st['step'] : 'unknown-step',
      status: WALK_STATUSES.includes(status as ReceiptWalkStatus)
        ? (status as ReceiptWalkStatus)
        : 'fail',
      detail: typeof st['detail'] === 'string' ? st['detail'] : null,
    };
  });
  return {
    valid: o['valid'] as boolean,
    receipt_id: o['receipt_id'] as string,
    project: o['project'] as string,
    steps,
  };
}

/**
 * Walk a receipt's proof chain: gateway signature → engine seal hash → snapshot.seq binding.
 *
 * Note the gateway returns HTTP 200 for a FAILED walk — a tampered chain is `valid: false`,
 * not a 4xx. So a non-ok HTTP status here means the call itself failed, which is a different
 * fact from "the receipt did not verify", and the two are reported separately.
 */
export async function verifyReceipt(receiptId: string, project = 'default'): Promise<VerifyResult> {
  if (!GATEWAY) {
    return {
      data: null,
      mode: 'unavailable',
      error: 'no compute-gateway base configured — receipt walk cannot run',
    };
  }
  const url =
    `${GATEWAY.replace(/\/$/, '')}/v1/engine-receipts/${encodeURIComponent(receiptId)}/verify` +
    `?project=${encodeURIComponent(project)}`;
  try {
    const res = await fetch(url, { headers: { accept: 'application/json' } });
    if (!res.ok) {
      return { data: null, mode: 'unavailable', error: `gateway ${res.status}` };
    }
    const walk = parseWalk(await res.json());
    if (!walk) {
      return { data: null, mode: 'unavailable', error: 'gateway returned an unrecognized verify-walk shape' };
    }
    return { data: walk, mode: 'live' };
  } catch (e) {
    return {
      data: null,
      mode: 'unavailable',
      error: `gateway unreachable: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
}

/**
 * Compile a question into ranked typed plans.
 *
 * FIXTURE-ONLY today. `question` is accepted so the call site is already the shape it will
 * keep, but no compiler runs: swapping in the live route means replacing the body of this
 * one function.
 *
 * It deliberately does NOT restamp the fixture with whatever the caller typed. Every span in
 * the fixture is a character offset into the fixture's OWN question; pasting a different
 * question over the top would leave `tokenSpan` pointing at the wrong characters, and the
 * plan tree would confidently highlight text that never produced it. A surface built to make
 * provenance honest cannot ship a provenance lie in its own fallback. A mismatched question
 * gets the fixture unchanged, plus an explicit note that the compiler did not run.
 */
export async function compileQuestion(question: string): Promise<CompileResult> {
  const q = question.trim();
  const mismatched = q.length > 0 && q !== FIXTURE_COMPILATION.question;
  return {
    data: FIXTURE_COMPILATION,
    mode: 'fixture',
    // The fixture compilation was never sealed by a gateway — say so, in the estate's own
    // honest-degradation vocabulary, instead of leaving the seal field conveniently absent.
    seal: FIXTURE_SEAL_DEGRADED,
    ...(mismatched
      ? {
          error:
            'No compiler ran: the fixture holds one compiled question, and its token spans are ' +
            'offsets into that question. Showing it unchanged rather than relabelling it with yours.',
        }
      : {}),
  };
}

/** The sealed walk the fixture surface uses to demonstrate a passing chain. */
export function fixtureWalk(): ReceiptVerifyWalk {
  return FIXTURE_WALK_VALID;
}
