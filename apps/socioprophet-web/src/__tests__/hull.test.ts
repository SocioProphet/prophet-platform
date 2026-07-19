import { describe, it, expect } from 'vitest';
import { convexHull, hullToPolygon, pointInPolygon } from '../data/hull';

describe('trade-area geometry', () => {
  it('hulls a point cloud to its outer boundary (interior points dropped)', () => {
    const pts: Array<[number, number]> = [[0, 0], [4, 0], [4, 4], [0, 4], [2, 2], [1, 1]]; // square + 2 interior
    const h = convexHull(pts);
    expect(h).toHaveLength(4); // the 4 corners only
    expect(h).toEqual(expect.arrayContaining([[0, 0], [4, 0], [4, 4], [0, 4]]));
  });

  it('returns the points unchanged below 3', () => {
    expect(convexHull([[0, 0], [1, 1]])).toHaveLength(2);
  });

  it('closes the polygon ring for GeoJSON', () => {
    const poly = hullToPolygon([[0, 0], [4, 0], [4, 4], [0, 4]]);
    expect(poly[0]!.length).toBe(5);
    expect(poly[0]![0]).toEqual(poly[0]![4]); // first == last
  });

  it('point-in-polygon: inside vs outside the catchment', () => {
    const ring: Array<[number, number]> = [[0, 0], [4, 0], [4, 4], [0, 4]];
    expect(pointInPolygon(2, 2, ring)).toBe(true);
    expect(pointInPolygon(5, 5, ring)).toBe(false);
    expect(pointInPolygon(-1, 2, ring)).toBe(false);
  });
});
