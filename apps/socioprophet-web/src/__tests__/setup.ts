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

// Working in-memory localStorage. Node 26 ships a NATIVE global `localStorage` that is a
// non-functional stub without --localstorage-file, and it shadows happy-dom's — so stores
// that persist (research, control-plane audit, …) silently no-op under test. Install a real
// one per test so persistence is exercised (production browsers use the real localStorage).
class MemoryStorage implements Storage {
  private m = new Map<string, string>();
  get length() { return this.m.size; }
  getItem(k: string) { return this.m.has(k) ? this.m.get(k)! : null; }
  setItem(k: string, v: string) { this.m.set(k, String(v)); }
  removeItem(k: string) { this.m.delete(k); }
  clear() { this.m.clear(); }
  key(i: number) { return [...this.m.keys()][i] ?? null; }
  [name: string]: unknown;
}

beforeEach(() => {
  const pinia = createPinia();
  setActivePinia(pinia);
  config.global.plugins = [pinia];
  const ls = new MemoryStorage();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: ls });
  if (typeof window !== 'undefined') Object.defineProperty(window, 'localStorage', { configurable: true, value: ls });
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
