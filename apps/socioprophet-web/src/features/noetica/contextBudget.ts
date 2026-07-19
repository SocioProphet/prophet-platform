// Noetica context-window budget model — turns the agent-machine's real per-turn context
// composition into a display breakdown (like a "what's in my context window" panel). The
// agent-machine already computes each named segment's tokens (server.ts ~4017–4061:
// MODEL_CONTEXT_TOKENS, TOKEN_BUDGET, systemTokens, msgTokens, and the named system-prompt
// parts). This module is DOM-free + pure so it unit-tests cleanly.

// The raw context payload the chat 'done' event carries (once the machine emits it).
export interface NoeticaContext {
  model: string;
  window: number;          // model context window in tokens (num_ctx / 180k)
  budget: number;          // usable budget (machine trims history past this)
  segments: Record<string, number>; // named segment → tokens (system, memory, grounding, graph, skills, goals, conversation)
}

export interface BudgetSlice { key: string; label: string; tokens: number; pct: number; color: string }
export interface BudgetView { model: string; window: number; budget: number; used: number; free: number; usedPct: number; slices: BudgetSlice[] }

// Fixed order + display metadata so colors/labels are stable across renders.
const META: Array<{ key: string; label: string; color: string }> = [
  { key: 'conversation', label: 'Conversation', color: '#e0655f' },
  { key: 'grounding', label: 'Grounding · RAG', color: '#e0894f' },
  { key: 'memory', label: 'Memory', color: '#e3b341' },
  { key: 'graph', label: 'Knowledge graph', color: '#5aa9e6' },
  { key: 'skills', label: 'Skills', color: '#8b8cff' },
  { key: 'goals', label: 'Goals · learner', color: '#4bbf73' },
  { key: 'system', label: 'System prompt', color: '#9aa0aa' },
];

export function buildBudgetView(ctx: NoeticaContext): BudgetView {
  const budget = Math.max(1, ctx.budget || ctx.window || 1);
  const slices: BudgetSlice[] = META
    .map((m) => ({ ...m, tokens: Math.max(0, ctx.segments?.[m.key] ?? 0) }))
    .filter((s) => s.tokens > 0)
    .map((s) => ({ ...s, pct: +((s.tokens / budget) * 100).toFixed(1) }))
    .sort((a, b) => b.tokens - a.tokens);
  const used = slices.reduce((sum, s) => sum + s.tokens, 0);
  const free = Math.max(0, budget - used);
  slices.push({ key: 'free', label: 'Free space', tokens: free, pct: +((free / budget) * 100).toFixed(1), color: '#3a3f47' });
  return { model: ctx.model, window: ctx.window, budget, used, free, usedPct: +((used / budget) * 100).toFixed(1), slices };
}

export function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k` : String(Math.round(n));
}
