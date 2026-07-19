import { describe, it, expect } from 'vitest';
import { situationForArea } from '../features/situations/mapSituation';
import { crossDomainClaims, type DomainInput } from '../gaia/crossDomain';
import { acsIncomeEvidence } from '../gaia/worldClaim';

const inputs: DomainInput[] = [
  { key: 'medianIncome', label: 'Median income', value: 82000, format: (v) => `$${Math.round(v / 1000)}k`, real: { source: acsIncomeEvidence('c'), confidence: 0.9, uncertaintyClass: 'low' } },
  { key: 'crimeRate', label: 'Crime', value: 40 }, // synthetic
];
const claims = crossDomainClaims('c', -73.98, 40.75, inputs);

describe('map situation (n-ary hyperedge from cross-domain claims)', () => {
  const s = situationForArea('Tract 5.01', 'c', claims, { events: ['Street fair'], competitors: 4 });

  it('binds one place + one claim member per domain into a single situation', () => {
    expect(s.members.filter((m) => m.type === 'place')).toHaveLength(1);
    expect(s.members.filter((m) => m.type === 'claim')).toHaveLength(2);
    expect(s.members.find((m) => m.type === 'event')?.label).toBe('Street fair');
    expect(s.members.find((m) => m.type === 'instrument')?.label).toContain('4 competitors');
  });

  it('claim members carry the Ω grade and real/illustrative flag', () => {
    const income = s.members.find((m) => m.label.startsWith('Median income'))!;
    expect(income.label).toContain('real');
    expect(income.role).toBe('Ω ACTIONABLE');
    const crime = s.members.find((m) => m.label.startsWith('Crime'))!;
    expect(crime.label).toContain('illustrative');
  });

  it('confidence reflects the real fraction, summary states the n-ary point', () => {
    expect(s.provenance.confidence).toBe(0.5); // 1 of 2 real
    expect(s.summary).toContain('not 2 disconnected links');
  });
});
