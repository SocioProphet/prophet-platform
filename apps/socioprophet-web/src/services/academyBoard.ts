// Academy mastery-check client → academy-board, the sovereign scoring service. The correct-answer
// index and explanation are NOT in this bundle — they live in the service, which returns a verdict
// only after a pick, each carrying a deterministic receipt. That's the whole point: grading is a
// real server authority (not client-side `pick === answer`), so a "mastered" claim is checkable and
// the answer key can't be read out of the page.
//
// Best-effort: if the board engine is unreachable the caller gets null and the UI degrades honestly
// ("grading unavailable") rather than inventing a verdict — we never re-ship the answers to fake it.
import { resolveBase } from '../config/cockpitRuntime';

const BOARD = resolveBase('board', 'VITE_BOARD_BASE', '/svc/board');

export interface BoardReceipt {
  id: string;
  verifier: 'academy-board';
  formula: string;
  at: string;
}

export interface ItemVerdict {
  itemId: string;
  correct: boolean;
  answer: number;   // authoritative correct index — revealed only by a graded response
  explain: string;
  concept: string;
  chunkRef: string; // captured-lecture segment the item is grounded in
  receipt: BoardReceipt;
}

export interface BoardVerdict {
  courseId: string;
  total: number;
  correct: number;
  scored: number;
  mastered: boolean;
  items: ItemVerdict[];
  receipt: BoardReceipt;
}

async function post<T>(path: string, body: unknown): Promise<T | null> {
  try {
    const res = await fetch(`${BOARD}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/** Grade a single pick. Returns the verdict (with receipt) or null if the board engine is down. */
export function gradeItem(courseId: string, itemId: string, pick: number): Promise<ItemVerdict | null> {
  return post<ItemVerdict>('/grade', { courseId, itemId, pick });
}

/** Grade a whole board submission; the board receipt binds every per-item verdict. */
export function gradeBoard(
  courseId: string,
  submissions: Array<{ itemId: string; pick: number }>,
): Promise<BoardVerdict | null> {
  return post<BoardVerdict>('/grade-board', { courseId, submissions });
}
