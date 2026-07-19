import { fetchT } from './http';
// Live air quality — real US-AQI from Open-Meteo's air-quality API (CAMS reanalysis),
// no key, CORS, GLOBAL (unlike the NYC-pinned crime/census layers). We sample a set
// of cell centroids in one batched call and nearest-assign to every cell, turning the
// synthetic "environment" air metric into a real measured field. Fails closed → the
// map keeps the illustrative air field. Same vendor as weatherLive.
export interface AirPoint { lon: number; lat: number; aqi: number }

const ENDPOINT = 'https://air-quality-api.open-meteo.com/v1/air-quality';

// points: [lon, lat][] — Open-Meteo takes comma-separated arrays and returns one
// location object per coordinate (or a single object for one coordinate).
export async function fetchAirQuality(points: Array<[number, number]>): Promise<AirPoint[] | null> {
  if (!points.length) return null;
  try {
    const lat = points.map((p) => p[1].toFixed(4)).join(',');
    const lon = points.map((p) => p[0].toFixed(4)).join(',');
    const url = `${ENDPOINT}?latitude=${lat}&longitude=${lon}&current=us_aqi`;
    const res = await fetchT(url, { headers: { accept: 'application/json' } }, 12000);
    if (!res.ok) return null;
    const j = await res.json();
    const arr = Array.isArray(j) ? j : [j];
    const out: AirPoint[] = [];
    arr.forEach((loc: { current?: { us_aqi?: number } }, i) => {
      const aqi = Number(loc?.current?.us_aqi);
      const pt = points[i];
      if (pt && Number.isFinite(aqi) && aqi > 0) out.push({ lon: pt[0], lat: pt[1], aqi });
    });
    return out.length ? out : null;
  } catch {
    return null;
  }
}
