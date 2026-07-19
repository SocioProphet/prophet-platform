// Live disruption → chain-node exposure. Pure geometry joining real disruption events
// (USGS quakes, NWS severe-weather alerts) to supply-chain providers by geography — the
// analytic that turns a generic risk feed into "which of MY nodes are exposed right now"
// (the Everstream / project44 move, bound to the governed chain). DOM-free, unit-testable.
import type { Provider } from '../../data/providersFixture';
import type { Quake } from '../../data/adapters/quakesLive';
import type { WxAlert } from '../../data/adapters/nwsAlertsLive';

// Great-circle distance in km.
export function haversineKm(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371;
  const dLat = ((bLat - aLat) * Math.PI) / 180;
  const dLon = ((bLon - aLon) * Math.PI) / 180;
  const s1 = Math.sin(dLat / 2);
  const s2 = Math.sin(dLon / 2);
  const a = s1 * s1 + Math.cos((aLat * Math.PI) / 180) * Math.cos((bLat * Math.PI) / 180) * s2 * s2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// A quake within radiusKm can plausibly disrupt a node (port closure, power, roads).
export const QUAKE_RADIUS_KM = 750;

export function nearestQuake(p: Provider, quakes: Quake[], radiusKm = QUAKE_RADIUS_KM): { quake: Quake; km: number } | null {
  let best: { quake: Quake; km: number } | null = null;
  for (const q of quakes) {
    const km = Math.round(haversineKm(p.geo.lat, p.geo.lon, q.lat, q.lon));
    if (km <= radiusKm && (!best || km < best.km)) best = { quake: q, km };
  }
  return best;
}

export interface ProviderExposure {
  provider: Provider;
  quake: { quake: Quake; km: number } | null;
  alert: WxAlert | null;
  severity: 'high' | 'medium';
}

// Join providers to disruptions. `alertsByProvider` carries NWS severe alerts already resolved
// for US providers (point API is US-only). Returns only EXPOSED providers, worst-first.
export function computeDisruptions(
  providers: Provider[],
  quakes: Quake[],
  alertsByProvider: Record<string, WxAlert>,
  radiusKm = QUAKE_RADIUS_KM,
): ProviderExposure[] {
  const out: ProviderExposure[] = [];
  for (const p of providers) {
    const quake = nearestQuake(p, quakes, radiusKm);
    const alert = alertsByProvider[p.id] ?? null;
    if (!quake && !alert) continue;
    const extreme = (alert && /extreme/i.test(alert.severity)) || (quake && quake.quake.mag >= 6);
    out.push({ provider: p, quake, alert, severity: extreme ? 'high' : 'medium' });
  }
  const rank = { high: 0, medium: 1 } as const;
  return out.sort((a, b) => rank[a.severity] - rank[b.severity] || (a.quake?.km ?? 1e9) - (b.quake?.km ?? 1e9));
}

// US bounding box — the NWS point API only covers US locations, so we only query it for these.
export function isUsProvider(p: Provider): boolean {
  return p.geo.lon >= -125 && p.geo.lon <= -66 && p.geo.lat >= 24 && p.geo.lat <= 50;
}
