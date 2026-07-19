import { describe, it, expect } from 'vitest';
import { crossDomainClaims, crossDomainPrompt, type DomainInput } from '../gaia/crossDomain';
import { acsIncomeEvidence } from '../gaia/worldClaim';

const inputs: DomainInput[] = [
  { key: 'medianIncome', label: 'Median income', value: 82000, format: (v) => `$${Math.round(v / 1000)}k`, real: { source: acsIncomeEvidence('c'), confidence: 0.9, uncertaintyClass: 'low' } },
  { key: 'crimeRate', label: 'Violent crime', value: 41 }, // synthetic
  { key: 'airQualityAqi', label: 'Air quality', value: 55 }, // synthetic
];

describe('cross-domain agentic brief', () => {
  const claims = crossDomainClaims('c', -73.98, 40.75, inputs);

  it('builds one governed claim per domain, admitted for real inputs, proposed for synthetic', () => {
    expect(claims).toHaveLength(3);
    const income = claims.find((c) => c.input.key === 'medianIncome')!;
    expect(income.claim.policy_status.status).toBe('admitted');
    expect(income.omega).toBe('ACTIONABLE');
    expect(claims.find((c) => c.input.key === 'crimeRate')!.claim.policy_status.status).toBe('proposed');
  });

  it('prompt puts REAL facts as ground truth and flags ILLUSTRATIVE ones', () => {
    const p = crossDomainPrompt('Tract 5.01', claims, 'Should I open a café here?');
    expect(p).toMatch(/REAL .*Median income: \$82k/);
    expect(p).toMatch(/US Census/); // real source named
    expect(p).toMatch(/ILLUSTRATIVE.*do NOT state as fact.*Violent crime: 41/);
    expect(p).toMatch(/weight the real figures over the illustrative/);
  });

  it('handles an all-synthetic area (no real facts yet)', () => {
    const p = crossDomainPrompt('X', crossDomainClaims('x', 0, 0, [inputs[1]!]), 'Q?');
    expect(p).toMatch(/REAL: none yet/);
  });
});
