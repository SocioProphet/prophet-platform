import { describe, it, expect } from 'vitest';
import { hexToRgb, hexColorData } from '../map/deckHexColors';

describe('deck.gl hex color prep', () => {
  it('parses 6- and 3-digit hex', () => {
    expect(hexToRgb('#4bbf73')).toEqual([75, 191, 115]);
    expect(hexToRgb('#fff')).toEqual([255, 255, 255]);
  });

  it('bins each cell into its class colour with an alpha channel', () => {
    const cells = [{ id: 'a', value: 10 }, { id: 'b', value: 50 }, { id: 'c', value: 90 }];
    const breaks = [40, 80]; // 3 classes: <40, 40–80, ≥80
    const colors = ['#000000', '#808080', '#ffffff'];
    const out = hexColorData(cells, breaks, colors, 200);
    expect(out[0]!.color).toEqual([0, 0, 0, 200]);       // 10 → class 0
    expect(out[1]!.color).toEqual([128, 128, 128, 200]); // 50 → class 1
    expect(out[2]!.color).toEqual([255, 255, 255, 200]); // 90 → class 2
    expect(out[0]!.h3).toBe('a');
  });

  it('clamps out-of-range values to the end classes', () => {
    const out = hexColorData([{ id: 'x', value: 999 }], [40, 80], ['#000000', '#808080', '#ffffff']);
    expect(out[0]!.color.slice(0, 3)).toEqual([255, 255, 255]);
  });
});
