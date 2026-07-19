import { fetchT } from './http';
// Live weather alerts — REAL active alerts from the U.S. National Weather Service
// (api.weather.gov, public, no key, CORS). Complements the already-live Open-Meteo
// conditions with authoritative watches/warnings for a point. Fails closed (null →
// no alerts shown). US-only (NWS). Ready to wire into WeatherMonitor.
export interface WxAlert { event: string; headline: string; severity: string; area: string; expires: string }

const BASE = 'https://api.weather.gov/alerts/active';

export async function fetchActiveAlerts(lat: number, lon: number, limit = 10): Promise<WxAlert[] | null> {
  try {
    const url = `${BASE}?point=${lat.toFixed(4)},${lon.toFixed(4)}&limit=${limit}`;
    const res = await fetchT(url, { headers: { accept: 'application/geo+json' } }, 10000);
    if (!res.ok) return null;
    const j = (await res.json()) as { features?: Array<{ properties?: { event?: string; headline?: string; severity?: string; areaDesc?: string; expires?: string } }> };
    if (!Array.isArray(j.features)) return null;
    const out: WxAlert[] = [];
    for (const f of j.features) {
      const p = f.properties; if (!p?.event) continue;
      out.push({ event: p.event, headline: p.headline ?? p.event, severity: p.severity ?? 'Unknown', area: p.areaDesc ?? '', expires: p.expires ?? '' });
    }
    // A point with no active alerts is a valid, meaningful answer ("all clear") — return
    // an empty array (not null) so the caller can say "no active alerts" vs "unreachable".
    return out;
  } catch {
    return null;
  }
}
