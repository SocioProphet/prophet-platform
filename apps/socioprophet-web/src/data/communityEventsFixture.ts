// Community events for the Map Workbench — the "civic calendar on the map":
// parades, marches, town halls, votes, cleanups, markets. UI-only; a future
// civic-calendar / permits adapter can emit the same shape.
export type EventType = 'parade' | 'march' | 'townhall' | 'festival' | 'cleanup' | 'vote' | 'market' | 'protest' | 'report';

export interface CommunityEvent {
  id: string;
  title: string;
  type: EventType;
  lon: number;
  lat: number;
  date: string;   // ISO date
  time: string;
  organizer: string;
  description: string;
}

export const EVENT_TYPES: Record<EventType, { label: string; icon: string; color: string }> = {
  parade: { label: 'Parade', icon: '🎉', color: '#e879f9' },
  march: { label: 'March', icon: '🚶', color: '#38bdf8' },
  townhall: { label: 'Town hall', icon: '🏛', color: '#fbbf24' },
  festival: { label: 'Festival', icon: '🎪', color: '#fb923c' },
  cleanup: { label: 'Cleanup', icon: '🧹', color: '#34d399' },
  vote: { label: 'Voting', icon: '🗳', color: '#818cf8' },
  market: { label: 'Market', icon: '🧺', color: '#a3e635' },
  protest: { label: 'Rally', icon: '📢', color: '#f87171' },
  report: { label: 'Citizen report', icon: '📸', color: '#f472b6' },
};

export const communityEvents: CommunityEvent[] = [
  { id: 'ev-pride', title: 'Pride Parade', type: 'parade', lon: -73.994, lat: 40.741, date: '2026-07-12', time: '11:00 AM', organizer: 'NYC Pride', description: 'Annual march up the avenue; road closures midtown to the Village.' },
  { id: 'ev-climate', title: 'Climate Action March', type: 'march', lon: -74.004, lat: 40.722, date: '2026-07-09', time: '2:00 PM', organizer: 'Sunrise Coalition', description: 'Rally at the park, march to City Hall for the resilience hearing.' },
  { id: 'ev-cb-townhall', title: 'Community Board 3 Town Hall', type: 'townhall', lon: -73.983, lat: 40.717, date: '2026-07-08', time: '6:30 PM', organizer: 'Community Board 3', description: 'Zoning + open-streets agenda; public comment period.' },
  { id: 'ev-union-mkt', title: 'Greenmarket', type: 'market', lon: -73.991, lat: 40.736, date: '2026-07-07', time: '8:00 AM', organizer: 'GrowNYC', description: 'Regional growers; SNAP/EBT accepted. Weekly.' },
  { id: 'ev-prospect-clean', title: 'Waterfront Cleanup', type: 'cleanup', lon: -74.018, lat: 40.702, date: '2026-07-11', time: '9:00 AM', organizer: 'Riverkeeper', description: 'Volunteer shoreline cleanup; gloves + bags provided.' },
  { id: 'ev-vote', title: 'Early Voting Opens', type: 'vote', lon: -73.941, lat: 40.686, date: '2026-07-10', time: '9:00 AM', organizer: 'Board of Elections', description: 'Early-voting site open through the 18th; check your poll site.' },
  { id: 'ev-street-fest', title: 'Avenue Street Festival', type: 'festival', lon: -73.978, lat: 40.724, date: '2026-07-13', time: '12:00 PM', organizer: 'Local BID', description: 'Vendors, music, food; avenue closed to traffic.' },
  { id: 'ev-tenant', title: 'Tenant Rights Rally', type: 'protest', lon: -73.996, lat: 40.751, date: '2026-07-09', time: '5:00 PM', organizer: 'Housing Justice NYC', description: 'Rally ahead of the rent-guidelines vote.' },
  { id: 'ev-book', title: 'Brooklyn Book Festival', type: 'festival', lon: -73.990, lat: 40.692, date: '2026-07-14', time: '10:00 AM', organizer: 'BK Book Festival', description: 'Authors, panels, indie presses across the plaza.' },
  { id: 'ev-bike', title: 'Bike Advocacy Ride', type: 'march', lon: -73.961, lat: 40.732, date: '2026-07-08', time: '7:00 PM', organizer: 'Transportation Alternatives', description: 'Group ride for protected-lane expansion.' },
  { id: 'ev-immig', title: 'Immigration Resource Forum', type: 'townhall', lon: -73.931, lat: 40.752, date: '2026-07-12', time: '3:00 PM', organizer: 'Legal Aid Society', description: 'Know-your-rights forum + free consultations.' },
  // Citizen journalism — geo-tagged reports, reporter carries a reputation Hat.
  { id: 'cr-flood', title: 'Storm-drain flooding on 9th', type: 'report', lon: -74.001, lat: 40.727, date: '2026-07-07', time: '7:42 AM', organizer: '@ada.newhope.social · Hat: local ✓', description: 'Recurring flooding at the corner after rain; two catch basins blocked. Photos attached. 3 corroborations.' },
  { id: 'cr-pothole', title: 'Pothole cluster, Atlantic Ave', type: 'report', lon: -73.978, lat: 40.684, date: '2026-07-06', time: '5:10 PM', organizer: '@grace.marketsdesk.io · Hat: verified', description: 'Six potholes over two blocks; cyclist hazard. Filed 311 #4471. 1 corroboration.' },
  { id: 'cr-market', title: 'New pop-up night market', type: 'report', lon: -73.958, lat: 40.716, date: '2026-07-09', time: '8:30 PM', organizer: '@skeptic.reader.bsky.social · Hat: local', description: 'Unpermitted vendor market drawing crowds; noise after 10pm. Unverified — awaiting corroboration.' },
  { id: 'cr-mural', title: 'Community mural unveiling', type: 'report', lon: -73.986, lat: 40.699, date: '2026-07-08', time: '2:00 PM', organizer: '@linus.dev · Hat: verified ✓', description: 'Youth-led mural completed on the underpass; positive turnout. 5 corroborations.' },
];
