import { describe, it, expect } from 'vitest';
import { prepTracts, tractIncomeAt, tractPopulationAt } from '../data/censusJoin';
import type { CensusFC } from '../data/adapters/censusLive';

// Two adjacent unit squares: A = [0,0]-[1,1] income 100k, B = [1,0]-[2,1] income 50k.
const fc: CensusFC = {
  type: 'FeatureCollection',
  features: [
    { type: 'Feature', properties: { geoid: 'A', name: 'A', medianIncome: 100000, population: 1000 },
      geometry: { type: 'Polygon', coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] } },
    { type: 'Feature', properties: { geoid: 'B', name: 'B', medianIncome: 50000, population: 1000 },
      geometry: { type: 'Polygon', coordinates: [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]] } },
    { type: 'Feature', properties: { geoid: 'Z', name: 'Z', medianIncome: 0, population: 0 }, // no income → dropped
      geometry: { type: 'Polygon', coordinates: [[[5, 5], [6, 5], [6, 6], [5, 6], [5, 5]]] } },
  ],
};

describe('census income join', () => {
  const tracts = prepTracts(fc);

  it('drops tracts with no income', () => {
    expect(tracts).toHaveLength(2);
  });

  it('assigns a point to the tract that contains it', () => {
    expect(tractIncomeAt(0.5, 0.5, tracts)).toBe(100000); // inside A
    expect(tractIncomeAt(1.5, 0.5, tracts)).toBe(50000);  // inside B
  });

  it('returns 0 for a point outside every tract', () => {
    expect(tractIncomeAt(-1, -1, tracts)).toBe(0);
    expect(tractIncomeAt(10, 10, tracts)).toBe(0);
  });

  it('also joins population by point-in-polygon', () => {
    expect(tractPopulationAt(0.5, 0.5, tracts)).toBe(1000); // tract A population
    expect(tractPopulationAt(-1, -1, tracts)).toBe(0);
  });

  it('handles MultiPolygon geometry', () => {
    const mp: CensusFC = { type: 'FeatureCollection', features: [
      { type: 'Feature', properties: { geoid: 'M', name: 'M', medianIncome: 77000, population: 1 },
        geometry: { type: 'MultiPolygon', coordinates: [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]] } },
    ] };
    expect(tractIncomeAt(0.5, 0.5, prepTracts(mp))).toBe(77000);
  });
});
