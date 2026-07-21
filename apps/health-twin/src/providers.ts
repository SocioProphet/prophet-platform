// Provider directory + care team. Two charts need this: the PATIENT chart shows who their doctors are —
// specialty, years in practice, credentials, verified — with a profile they can review; the DOCTOR chart
// shows the care team on a patient's record. Providers are derived from the encounters/records that
// reference them. Verified = a real, licensed clinician (the trust primitive the community depends on).
import { ENCOUNTERS } from './data.js';

export interface Provider {
  id: string; name: string; specialty: string; role: string;
  since: number;          // year they began practising
  credentials: string;    // e.g. "MD, FACC"
  org: string; location: string;
  npi?: string;           // National Provider Identifier (verification anchor)
  verified: boolean;      // credential + license verified
  match: string[];        // strings that appear in a record's provider field
}

export const PROVIDERS: Provider[] = [
  { id: 'prov-rivera', name: 'Dr. Ana Rivera', specialty: 'Cardiology', role: 'Cardiologist', since: 2009, credentials: 'MD, FACC', org: 'Bay Cardiology Associates', location: 'San Francisco, CA', npi: '1063494177', verified: true, match: ['rivera'] },
  { id: 'prov-okafor', name: 'Dr. James Okafor', specialty: 'Family Medicine', role: 'Primary care physician', since: 2014, credentials: 'MD', org: 'Mission Family Health', location: 'San Francisco, CA', npi: '1730346588', verified: true, match: ['okafor'] },
  { id: 'prov-labcorp', name: 'LabCorp', specialty: 'Clinical Laboratory', role: 'Diagnostic lab', since: 1978, credentials: 'CLIA-certified', org: 'Laboratory Corporation of America', location: 'Burlington, NC', verified: true, match: ['labcorp'] },
  { id: 'prov-radiology', name: 'Bay Imaging — Radiology', specialty: 'Radiology', role: 'Imaging center', since: 1996, credentials: 'ACR-accredited', org: 'Bay Imaging', location: 'San Francisco, CA', verified: true, match: ['radiology'] },
  { id: 'prov-peds-er', name: 'Children’s Hospital ER', specialty: 'Emergency Medicine', role: 'Emergency department', since: 1985, credentials: 'ACS-verified', org: 'Children’s Hospital', location: 'Oakland, CA', verified: true, match: ['pediatric er', 'children'] },
];

export const yearsInPractice = (p: Provider): number => Math.max(0, new Date().getFullYear() - p.since);

const find = (provider: string): Provider | undefined => {
  const p = provider.toLowerCase();
  return PROVIDERS.find((prov) => prov.match.some((m) => p.includes(m)));
};

// The care team on this record: which providers appear, when they were last seen, how many visits.
export function careTeam() {
  const seen = new Map<string, { provider: Provider; visits: number; lastSeen: string; firstSeen: string }>();
  for (const e of ENCOUNTERS) {
    const prov = find(e.provider);
    if (!prov) continue;
    const cur = seen.get(prov.id);
    if (cur) { cur.visits++; if (e.date > cur.lastSeen) cur.lastSeen = e.date; if (e.date < cur.firstSeen) cur.firstSeen = e.date; }
    else seen.set(prov.id, { provider: prov, visits: 1, lastSeen: e.date, firstSeen: e.date });
  }
  return [...seen.values()]
    .sort((a, b) => (a.lastSeen < b.lastSeen ? 1 : -1))
    .map((x) => ({ ...x.provider, yearsInPractice: yearsInPractice(x.provider), visits: x.visits, lastSeen: x.lastSeen, firstSeen: x.firstSeen }));
}

export const provider = (id: string) => {
  const p = PROVIDERS.find((x) => x.id === id);
  return p ? { ...p, yearsInPractice: yearsInPractice(p) } : null;
};
export const directory = () => PROVIDERS.map((p) => ({ ...p, yearsInPractice: yearsInPractice(p) }));
