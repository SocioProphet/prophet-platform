import { describe, it, expect } from 'vitest';
import { buildBudgetView, fmtTokens } from '../features/noetica/contextBudget';

describe('noetica context budget', () => {
  it('breaks the budget into named slices + free space, sorted by size, summing to budget', () => {
    const v = buildBudgetView({ model: 'qwen2.5:7b', window: 16384, budget: 11469, segments: { system: 1200, memory: 800, grounding: 2600, graph: 300, skills: 150, goals: 90, conversation: 3400 } });
    expect(v.slices[0].key).toBe('conversation'); // largest first
    expect(v.slices.at(-1)!.key).toBe('free');     // free space last
    expect(v.used).toBe(1200 + 800 + 2600 + 300 + 150 + 90 + 3400);
    expect(v.free).toBe(v.budget - v.used);
    expect(v.slices.reduce((s, x) => s + x.tokens, 0)).toBe(v.budget); // used + free = budget
    expect(v.usedPct).toBeGreaterThan(0);
  });
  it('drops zero segments and formats tokens', () => {
    const v = buildBudgetView({ model: 'm', window: 8192, budget: 5734, segments: { system: 500, graph: 0, conversation: 0 } });
    expect(v.slices.filter((s) => s.key !== 'free').map((s) => s.key)).toEqual(['system']);
    expect(fmtTokens(5734)).toBe('5.7k');
    expect(fmtTokens(120000)).toBe('120k');
  });
});
