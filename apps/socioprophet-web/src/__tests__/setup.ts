/**
 * Vitest global setup.
 *
 * - Stubs maplibre-gl so tests run in happy-dom without WebGL.
 * - Installs a fresh Pinia before each test, so components that use the shared
 *   stores (portfolio, cockpit, …) mount without each test wiring pinia by hand.
 */
import { beforeEach, vi } from 'vitest';
import { config } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';

beforeEach(() => {
  const pinia = createPinia();
  setActivePinia(pinia);
  config.global.plugins = [pinia];
});

class MapStub {
  addControl() {}
  easeTo() {}
  flyTo() {}
  fitBounds() {}
  on() {}
  getSource(): undefined { return undefined; }
  addSource() {}
  addLayer() {}
  getZoom() { return 1; }
  remove() {}
}

class MarkerStub {
  setLngLat() { return this; }
  setPopup() { return this; }
  addTo() { return this; }
  getElement() { return document.createElement('div'); }
  remove() {}
}

class PopupStub {
  setText() { return this; }
}

class NavigationControlStub {}
class ScaleControlStub {}
class FullscreenControlStub {}
class GeolocateControlStub { on() {} }

class LngLatBoundsStub {
  extend() { return this; }
  isEmpty() { return true; }
}

vi.mock('maplibre-gl', () => ({
  default: {
    Map: MapStub,
    Marker: MarkerStub,
    Popup: PopupStub,
    NavigationControl: NavigationControlStub,
    ScaleControl: ScaleControlStub,
    FullscreenControl: FullscreenControlStub,
    GeolocateControl: GeolocateControlStub,
    LngLatBounds: LngLatBoundsStub,
  },
  Map: MapStub,
  Marker: MarkerStub,
  Popup: PopupStub,
  NavigationControl: NavigationControlStub,
  ScaleControl: ScaleControlStub,
  LngLatBounds: LngLatBoundsStub,
}));
