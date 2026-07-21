// The board engine: deterministic, server-authoritative grading with a content-id receipt.
// A verdict is a fact about (course, item, pick) that any party can recompute and check —
// the same proof-carrying posture as the rest of the estate (portfolio-agent, holmes).

import { ANSWER_KEY, type KeyItem } from './keys.js';

// djb2 — a small, dependency-free content hash. The receipt id is a function of the exact
// inputs + verdict, so an identical submission yields an identical receipt (deterministic),
// and any tampering with what was asked/answered changes the id.
function djb2(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) & 0xffffffff;
  return (h >>> 0).toString(16).padStart(8, '0');
}

export interface Receipt {
  id: string;
  verifier: 'academy-board';
  formula: string;
  at: string;
}

export interface ItemVerdict {
  itemId: string;
  correct: boolean;
  answer: number;     // the authoritative correct index — only revealed by a graded response
  explain: string;
  concept: string;
  chunkRef: string;   // what the mastery was measured against
  receipt: Receipt;
}

export interface BoardVerdict {
  courseId: string;
  total: number;
  correct: number;
  scored: number;     // how many of the board's items this submission covered
  mastered: boolean;  // every item on the board answered correctly
  items: ItemVerdict[];
  receipt: Receipt;
}

function key(courseId: string): Record<string, KeyItem> | null {
  return ANSWER_KEY[courseId] ?? null;
}

export function courseKnown(courseId: string): boolean {
  return key(courseId) !== null;
}

// Grade one pick. Returns null for an unknown course/item so the caller answers 404 rather
// than inventing a verdict.
export function gradeItem(courseId: string, itemId: string, pick: number): ItemVerdict | null {
  const k = key(courseId);
  const it = k?.[itemId];
  if (!it) return null;
  const correct = pick === it.answer;
  const at = new Date().toISOString();
  const receipt: Receipt = {
    id: `bd-${djb2([courseId, itemId, String(pick), String(it.answer), it.chunkRef].join('|'))}`,
    verifier: 'academy-board',
    formula: 'verdict = (pick === answer); grounded in ' + it.chunkRef,
    at,
  };
  return { itemId, correct, answer: it.answer, explain: it.explain, concept: it.concept, chunkRef: it.chunkRef, receipt };
}

// Grade a whole board submission. The board receipt binds the per-item verdicts, so a "mastered"
// claim is itself checkable — its id is a function of every (item, pick) and the resulting score.
export function gradeBoard(courseId: string, submissions: Array<{ itemId: string; pick: number }>): BoardVerdict | null {
  const k = key(courseId);
  if (!k) return null;
  const total = Object.keys(k).length;
  const items: ItemVerdict[] = [];
  for (const s of submissions) {
    const v = gradeItem(courseId, s.itemId, s.pick);
    if (v) items.push(v);
  }
  const correct = items.filter((v) => v.correct).length;
  const scored = items.length;
  const mastered = scored === total && correct === total;
  const at = new Date().toISOString();
  const receipt: Receipt = {
    id: `bd-board-${djb2([courseId, String(total), String(correct), ...items.map((v) => `${v.itemId}:${v.correct ? 1 : 0}`)].join('|'))}`,
    verifier: 'academy-board',
    formula: `score = Σ(pick === answer) over ${total} grounded items; mastered = score === total`,
    at,
  };
  return { courseId, total, correct, scored, mastered, items, receipt };
}
