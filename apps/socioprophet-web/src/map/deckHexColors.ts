// Pure color prep for the GPU (deck.gl) hex renderer — kept separate from the WebGL
// wiring so it's unit-testable. Bins each cell's value into a class and returns the
// H3 index + RGBA the H3HexagonLayer draws. Mirrors the MapLibre choropleth so GPU
// mode looks identical, just able to push 100k+ hexes.
import { classOf } from '../data/classify';

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '');
  const s = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16), parseInt(s.slice(4, 6), 16)];
}

export interface DeckHex { h3: string; value: number; color: [number, number, number, number] }

export function hexColorData(
  cells: Array<{ id: string; value: number }>,
  breaks: number[],
  colorsHex: string[],
  alpha = 205,
): DeckHex[] {
  return cells.map((c) => {
    const k = Math.min(colorsHex.length - 1, Math.max(0, classOf(c.value, breaks)));
    const [r, g, b] = hexToRgb(colorsHex[k]!);
    return { h3: c.id, value: c.value, color: [r, g, b, alpha] };
  });
}
