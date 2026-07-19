// Shared trading book — the integration seam that ties Market Monitor, the
// Portfolio surface, and the Algorithmic Trading board to ONE functional state.
// Paper-trading (deterministic, client-side, persisted) so orders placed on the
// market board show up as real positions + P&L on the portfolio board and feed
// the same blotter the algo strategies post into. No live venue; a future
// execution adapter can replace fillOrder() without touching consumers.
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

export type Side = 'buy' | 'sell';
export interface Order {
  id: string;
  ts: number;
  symbol: string;
  name: string;
  side: Side;
  qty: number;
  price: number;
  source: string; // 'manual' | 'algo:<strategy>' | …
}
export interface Position {
  symbol: string;
  name: string;
  qty: number;
  avgCost: number;
  realized: number;
}

const STARTING_CASH = 1_000_000;
const STORE_KEY = 'sp-portfolio-v1';

function loadOrders(): Order[] {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Order[];
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

export const usePortfolio = defineStore('portfolio', () => {
  const orders = ref<Order[]>(loadOrders());

  function persist() {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(orders.value)); } catch { /* */ }
  }

  // Place + immediately fill a paper order (risk-gated: no shorting below zero).
  function placeOrder(o: Omit<Order, 'id' | 'ts'>): { ok: boolean; reason?: string } {
    if (o.qty <= 0 || o.price <= 0) return { ok: false, reason: 'Quantity and price must be positive.' };
    if (o.side === 'sell') {
      const held = positions.value.find((p) => p.symbol === o.symbol)?.qty ?? 0;
      if (o.qty > held) return { ok: false, reason: `Cannot sell ${o.qty} — only ${held} held.` };
    } else if (o.qty * o.price > cash.value) {
      return { ok: false, reason: 'Insufficient cash for this order.' };
    }
    orders.value = [...orders.value, { ...o, id: `ord-${Date.now()}-${orders.value.length}`, ts: Date.now() }];
    persist();
    return { ok: true };
  }

  function reset() { orders.value = []; persist(); }

  // Fold the blotter (oldest→newest) into net positions with avg-cost accounting.
  const positions = computed<Position[]>(() => {
    const bySym = new Map<string, Position>();
    for (const o of [...orders.value].sort((a, b) => a.ts - b.ts)) {
      const p = bySym.get(o.symbol) ?? { symbol: o.symbol, name: o.name, qty: 0, avgCost: 0, realized: 0 };
      if (o.side === 'buy') {
        const newQty = p.qty + o.qty;
        p.avgCost = newQty ? (p.avgCost * p.qty + o.price * o.qty) / newQty : 0;
        p.qty = newQty;
      } else {
        p.realized += (o.price - p.avgCost) * Math.min(o.qty, p.qty);
        p.qty = Math.max(0, p.qty - o.qty);
      }
      p.name = o.name;
      bySym.set(o.symbol, p);
    }
    return [...bySym.values()].filter((p) => p.qty > 0 || p.realized !== 0);
  });

  const cash = computed<number>(() =>
    orders.value.reduce((c, o) => c + (o.side === 'buy' ? -1 : 1) * o.qty * o.price, STARTING_CASH),
  );
  const realized = computed<number>(() => positions.value.reduce((s, p) => s + p.realized, 0));
  const blotter = computed<Order[]>(() => [...orders.value].sort((a, b) => b.ts - a.ts));

  // Mark-to-market against a live price lookup (passed from whoever holds quotes).
  function marketValue(priceOf: (symbol: string) => number | undefined): number {
    return positions.value.reduce((s, p) => s + (priceOf(p.symbol) ?? p.avgCost) * p.qty, 0);
  }
  function unrealized(priceOf: (symbol: string) => number | undefined): number {
    return positions.value.reduce((s, p) => s + ((priceOf(p.symbol) ?? p.avgCost) - p.avgCost) * p.qty, 0);
  }
  function positionFor(symbol: string): Position | undefined {
    return positions.value.find((p) => p.symbol === symbol);
  }

  return {
    orders, positions, cash, realized, blotter, startingCash: STARTING_CASH,
    placeOrder, reset, marketValue, unrealized, positionFor,
  };
});
