// GPU hex renderer via deck.gl's MapboxOverlay + H3HexagonLayer, layered on the
// existing MapLibre map. Lets the civic choropleth scale to 100k+ hexes on the GPU
// (the rendering-scale turf: Mapbox/deck.gl). Thin wrapper — the color prep lives in
// deckHexColors.ts (unit-tested); this file is the WebGL glue (not unit-testable in jsdom).
import { MapboxOverlay } from '@deck.gl/mapbox';
import { H3HexagonLayer } from '@deck.gl/geo-layers';
import type { Map as MlMap, IControl } from 'maplibre-gl';
import type { DeckHex } from './deckHexColors';

let overlay: MapboxOverlay | null = null;

function ensureOverlay(map: MlMap): MapboxOverlay {
  if (!overlay) {
    overlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(overlay as unknown as IControl); // MapboxOverlay implements maplibre's IControl
  }
  return overlay;
}

export function renderDeckHexes(map: MlMap, data: DeckHex[], opacity = 0.85): void {
  const ov = ensureOverlay(map);
  ov.setProps({
    layers: [
      new H3HexagonLayer<DeckHex>({
        id: 'deck-civic-hex',
        data,
        getHexagon: (d) => d.h3,
        getFillColor: (d) => d.color,
        getLineColor: [10, 12, 16, 110],
        lineWidthMinPixels: 0.4,
        stroked: true,
        filled: true,
        extruded: false,
        opacity,
        pickable: false,
        updateTriggers: { getFillColor: data },
      }),
    ],
  });
}

export function clearDeckHexes(): void {
  overlay?.setProps({ layers: [] });
}
