// MLS listings — individual for-sale / for-rent inventory to plot OVER the
// aggregate real-estate choropleth (aggregate = context, points = actionable
// inventory). UI-only; a real MLS/CoStar adapter emits the same shape.
export interface Listing {
  id: string;
  lon: number;
  lat: number;
  type: 'sale' | 'rent';
  price: number;         // sale price, or monthly rent
  beds: number;
  baths: number;
  sqft: number;
  capRate: number;       // gross yield %
  status: 'active' | 'pending';
  address: string;
}

export const LISTINGS: Listing[] = [
  { id: 'l1', lon: -73.995, lat: 40.735, type: 'sale', price: 1250000, beds: 2, baths: 2, sqft: 1100, capRate: 4.1, status: 'active', address: '112 W 12th St #4B' },
  { id: 'l2', lon: -73.986, lat: 40.719, type: 'sale', price: 895000, beds: 1, baths: 1, sqft: 720, capRate: 4.8, status: 'active', address: '340 E Houston St #2' },
  { id: 'l3', lon: -74.008, lat: 40.726, type: 'rent', price: 4200, beds: 2, baths: 1, sqft: 900, capRate: 5.2, status: 'active', address: '55 Bethune St #3R' },
  { id: 'l4', lon: -73.978, lat: 40.684, type: 'sale', price: 1650000, beds: 3, baths: 2, sqft: 1600, capRate: 3.9, status: 'pending', address: '88 Dean St, Brooklyn' },
  { id: 'l5', lon: -73.958, lat: 40.716, type: 'rent', price: 3100, beds: 1, baths: 1, sqft: 650, capRate: 6.1, status: 'active', address: '19 Metropolitan Ave #2' },
  { id: 'l6', lon: -74.015, lat: 40.705, type: 'sale', price: 2350000, beds: 3, baths: 3, sqft: 2100, capRate: 3.4, status: 'active', address: '2 Battery Pl #14A' },
  { id: 'l7', lon: -73.99, lat: 40.75, type: 'rent', price: 5600, beds: 3, baths: 2, sqft: 1350, capRate: 4.6, status: 'active', address: '450 W 42nd St #28C' },
  { id: 'l8', lon: -73.945, lat: 40.68, type: 'sale', price: 720000, beds: 2, baths: 1, sqft: 980, capRate: 6.8, status: 'active', address: '1200 Bergen St, Brooklyn' },
  { id: 'l9', lon: -74.032, lat: 40.72, type: 'rent', price: 2650, beds: 1, baths: 1, sqft: 600, capRate: 5.9, status: 'pending', address: '70 Grand St, Jersey City' },
  { id: 'l10', lon: -73.982, lat: 40.744, type: 'sale', price: 1080000, beds: 1, baths: 1, sqft: 780, capRate: 4.3, status: 'active', address: '5 E 22nd St #12F' },
  { id: 'l11', lon: -73.968, lat: 40.699, type: 'sale', price: 1420000, beds: 2, baths: 2, sqft: 1250, capRate: 4.5, status: 'active', address: '11 Hoyt St #33B, Brooklyn' },
  { id: 'l12', lon: -74.006, lat: 40.713, type: 'rent', price: 3800, beds: 2, baths: 1, sqft: 850, capRate: 5.0, status: 'active', address: '25 Murray St #5' },
  { id: 'l13', lon: -73.936, lat: 40.712, type: 'sale', price: 640000, beds: 1, baths: 1, sqft: 700, capRate: 7.2, status: 'active', address: '54-20 Vernon Blvd, Queens' },
  { id: 'l14', lon: -74.05, lat: 40.73, type: 'rent', price: 2900, beds: 2, baths: 1, sqft: 820, capRate: 6.3, status: 'active', address: '155 Washington St, JC' },
  { id: 'l15', lon: -73.992, lat: 40.729, type: 'sale', price: 1780000, beds: 2, baths: 2, sqft: 1400, capRate: 3.8, status: 'pending', address: '21 E 12th St #PH' },
  { id: 'l16', lon: -73.973, lat: 40.676, type: 'rent', price: 3400, beds: 2, baths: 2, sqft: 1050, capRate: 5.5, status: 'active', address: '626 Flatbush Ave #7C' },
];
