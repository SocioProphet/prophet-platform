// Fixture for the Law & Regulation docket (/law/*). UI-only. A future legal-intake
// lane can populate the same Docket shape. Redline = ordered diff segments.
// Enriched with the fields a real regulatory product needs: who issued it, when it
// bites, who it affects (→ cross-links into Markets/Economy), and what it cites.
export type DocketType = 'rule' | 'bill' | 'case';
export type DocketStatus = 'comment' | 'pending' | 'enacted' | 'open';

export interface RedlineSeg { type: 'ctx' | 'add' | 'del'; text: string }
export interface Citation { cite: string; title: string; docketId?: string }
export interface Affects { sectors?: string[]; symbols?: string[]; topics?: string[] }

export interface Docket {
  id: string;
  cite: string;
  title: string;
  type: DocketType;
  jurisdiction: string;
  status: DocketStatus;
  updated: string;
  summary: string;
  provenanceHash: string;
  redline: RedlineSeg[];
  // Enrichment
  agency: string;
  tags: string[];
  affects: Affects;
  impact: string;
  citations: Citation[];
  commentDeadline?: string;
  effectiveDate?: string;
  url?: string; // real source link when the docket is live (e.g. federalregister.gov)
  supersededBy?: string; // docketId of a later authority that supersedes this (in whole or part)
}

export const dockets: Docket[] = [
  {
    id: 'd-provenance', cite: 'ODG-2026-114', title: 'Model-Provenance Disclosure Rule', type: 'rule', jurisdiction: 'Federal', status: 'comment', updated: '2026-07-03T12:20:00-04:00',
    summary: 'Would require deployers to attach verifiable provenance to automated decisions above a risk threshold. Comment period open (60 days).',
    agency: 'Office of Digital Governance',
    tags: ['provenance', 'automated-decisions', 'disclosure', 'ai-governance'],
    affects: { sectors: ['Technology'], symbols: ['NVDA', 'MSFT', 'GOOGL'], topics: ['Provenance Rule', 'Automated Decisions'] },
    impact: 'AI deployers making high-impact automated decisions must attach a verifiable provenance record and make it available to the subject within 30 days. Raises the compliance bar for large model operators.',
    citations: [{ cite: '§ 2(c)', title: 'Risk-threshold definition' }, { cite: 'WG-AUD-07', title: 'Audit-Trail Guidance', docketId: 'd-audit' }],
    commentDeadline: '2026-09-01T23:59:00-04:00',
    provenanceHash: 'sha256:odg114…9c2', redline: [
      { type: 'ctx', text: '§ 4. Automated decision systems.' },
      { type: 'ctx', text: '(a) A deployer of an automated decision system shall—' },
      { type: 'del', text: '  (1) maintain internal documentation of the system’s logic.' },
      { type: 'add', text: '  (1) attach a verifiable provenance record to each decision above the risk threshold defined in § 2(c).' },
      { type: 'add', text: '  (2) make the provenance record available to the subject on request within 30 days.' },
      { type: 'ctx', text: '(b) The threshold in § 2(c) applies only to high-impact determinations.' },
    ],
  },
  {
    id: 'd-audit', cite: 'WG-AUD-07', title: 'Audit-Trail Guidance (Cross-Jurisdiction)', type: 'rule', jurisdiction: 'International', status: 'pending', updated: '2026-07-03T09:45:00-04:00',
    summary: 'Recommends hash-sealed, replayable audit trails sufficient to reconstruct each high-stakes automated decision, interoperable with existing evidence frameworks.',
    agency: 'Cross-Jurisdiction Working Group',
    tags: ['audit-trail', 'evidence', 'interoperability'],
    affects: { sectors: ['Technology', 'Financials'], symbols: ['MSFT', 'JPM'], topics: ['Audit Trail'] },
    impact: 'Regulated operators would have to retain reconstruction-grade logs — not summaries — for every high-stakes automated decision. For firms like MSFT and JPM running automated decisioning at scale, that is a materially higher retention and storage burden, and shifts the evidentiary default from "documented" to "replayable".',
    citations: [
      { cite: 'ODG-2026-114', title: 'Model-Provenance Disclosure Rule', docketId: 'd-provenance' },
      { cite: 'EV-STD-3', title: 'Digital Evidence Interoperability Standard', docketId: 'd-evstd' },
    ],
    supersededBy: 'd-liability',
    effectiveDate: 'on adoption',
    provenanceHash: 'sha256:wgaud07…41a', redline: [
      { type: 'ctx', text: 'Recommendation 3 — Evidentiary retention.' },
      { type: 'del', text: '  Systems should retain logs for a reasonable period.' },
      { type: 'add', text: '  Systems shall retain hash-sealed, replayable audit trails sufficient to reconstruct each high-stakes decision.' },
      { type: 'ctx', text: 'Recommendation 4 — Interoperability with existing evidence frameworks.' },
    ],
  },
  {
    id: 'd-data', cite: 'HR-2026-882', title: 'Cross-Border Data Flows Framework Act', type: 'bill', jurisdiction: 'Federal', status: 'pending', updated: '2026-07-03T13:40:00-04:00',
    summary: 'Establishes transfer safeguards and an adequacy-review process; provisional framework pending ratification.',
    agency: 'House Commerce Committee',
    tags: ['data-transfer', 'adequacy', 'cross-border', 'privacy'],
    affects: { sectors: ['Technology', 'Financials'], symbols: ['MSFT', 'GOOGL', 'META'], topics: ['Cross-border Data'] },
    impact: 'Cross-border data transfers permitted only under an in-force adequacy determination, reviewed every three years. Directly affects cloud and platform operators with international data flows.',
    citations: [],
    effectiveDate: 'upon ratification',
    provenanceHash: 'sha256:hr882…7be', redline: [
      { type: 'ctx', text: 'Sec. 2. Transfer safeguards.' },
      { type: 'add', text: '  (a) A transfer to a third country is permitted only where an adequacy determination is in force.' },
      { type: 'add', text: '  (b) The Commission shall review adequacy determinations every three years.' },
      { type: 'ctx', text: 'Sec. 3. Effective date — upon ratification.' },
    ],
  },
  {
    id: 'd-grid', cite: 'IC-DIR-19', title: 'Shared Grid Interconnect Directive', type: 'rule', jurisdiction: 'Regional', status: 'enacted', updated: '2026-07-03T11:30:00-04:00',
    summary: 'Sets a phased timeline for a shared interconnect; cites resilience and price stability.',
    agency: 'Regional Energy Commission',
    tags: ['grid', 'interconnect', 'energy', 'resilience'],
    affects: { sectors: ['Energy', 'Utilities'], symbols: ['XOM', 'COPPER'], topics: ['grid'] },
    impact: 'Phased shared interconnect (Phase I 24 months, Phase II 48 months). Improves regional resilience and price stability; pulls forward grid + electrification demand.',
    citations: [],
    effectiveDate: '2026-06-01T00:00:00-04:00',
    provenanceHash: 'sha256:icdir19…0d5', redline: [
      { type: 'ctx', text: 'Article 5. Phased timeline.' },
      { type: 'del', text: '  Interconnection shall be completed as soon as practicable.' },
      { type: 'add', text: '  Phase I shall complete within 24 months; Phase II within 48 months of entry into force.' },
    ],
  },
  {
    id: 'd-corridor', cite: 'CASE-4471', title: 'In re Humanitarian Corridor Access', type: 'case', jurisdiction: 'International', status: 'open', updated: '2026-07-03T09:10:00-04:00',
    summary: 'Dispute over inspection and routing terms for aid convoys; corridor reopened under interim terms.',
    agency: 'International Tribunal',
    tags: ['humanitarian', 'logistics', 'routing'],
    affects: { sectors: [], symbols: [], topics: ['Humanitarian Corridor'] },
    impact: 'Interim routing and inspection terms allow convoys to transit pending final determination — a logistics reopening with supply-route implications.',
    citations: [],
    provenanceHash: 'sha256:case4471…8fa', redline: [
      { type: 'ctx', text: 'Interim order — routing and inspection.' },
      { type: 'add', text: '  Convoys may transit under the inspection protocol in Annex B pending final determination.' },
    ],
  },
  {
    id: 'd-evstd', cite: 'EV-STD-3', title: 'Digital Evidence Interoperability Standard', type: 'rule', jurisdiction: 'International', status: 'enacted', updated: '2026-05-12T09:00:00-04:00',
    summary: 'Common schema and exchange format for machine-generated evidence so audit records are portable across jurisdictions and tribunals.',
    agency: 'International Standards Board',
    tags: ['evidence', 'interoperability', 'standard'],
    affects: { sectors: ['Technology', 'Financials'], symbols: ['MSFT'], topics: ['Evidence Standard', 'Interoperability'] },
    impact: 'Sets the interchange format later guidance builds on. Once adopted, evidence produced under one regime is admissible under another — lowering the cost of cross-border compliance but fixing the record schema vendors must emit.',
    citations: [],
    effectiveDate: '2026-06-01T00:00:00-04:00',
    provenanceHash: 'sha256:evstd3…7b1', redline: [
      { type: 'ctx', text: 'Clause 2 — Record schema.' },
      { type: 'add', text: '  Conforming systems shall emit evidence in the EV-STD-3 envelope (subject, decision, inputs-hash, replay-seed).' },
    ],
  },
  {
    id: 'd-liability', cite: 'DIR-2026-ASL', title: 'Automated-Systems Liability Directive', type: 'bill', jurisdiction: 'International', status: 'pending', updated: '2026-07-01T11:30:00-04:00',
    summary: 'Establishes a rebuttable presumption of fault where an operator cannot produce a replayable record for a challenged automated decision; supersedes the retention recommendation in WG-AUD-07 Rec 3 with a binding standard.',
    agency: 'Cross-Jurisdiction Working Group',
    tags: ['liability', 'automated-decisions', 'audit-trail', 'evidence'],
    affects: { sectors: ['Technology', 'Financials', 'Healthcare'], symbols: ['MSFT', 'JPM'], topics: ['Automated Decisions', 'Liability'] },
    impact: 'Turns the audit-trail recommendation into a liability rule: no replayable record means the operator, not the claimant, carries the burden. This is the operative instrument that supersedes the earlier voluntary guidance — firms that treated WG-AUD-07 as optional are now exposed.',
    citations: [{ cite: 'WG-AUD-07', title: 'Audit-Trail Guidance (Cross-Jurisdiction)', docketId: 'd-audit' }],
    commentDeadline: '2026-08-15T23:59:00-04:00',
    provenanceHash: 'sha256:dirasl…c40', redline: [
      { type: 'ctx', text: 'Article 4 — Burden of proof.' },
      { type: 'del', text: '  Claimant must establish the system acted wrongfully.' },
      { type: 'add', text: '  Where the operator cannot produce a replayable record under EV-STD-3, fault is presumed and the operator bears the burden of rebuttal.' },
    ],
  },

  // ── Case-law citator chain — the canonical Shepard's demo: a foundational precedent,
  // a decision that distinguishes it, and a later decision that OVERRULES it. The citator
  // flags the precedent red ("overruled") and the depth-of-treatment tally shows the split.
  {
    id: 'd-meridian', cite: 'Meridian Logistics v. State', title: 'Meridian Logistics v. State', type: 'case', jurisdiction: 'Federal', status: 'enacted', updated: '2024-03-11T10:00:00-04:00',
    summary: 'Held that an operator of an automated decision system is liable only where the claimant proves the system departed from a documented internal standard.',
    agency: 'Court of Appeals (9th Cir.)',
    tags: ['automated-decisions', 'liability', 'precedent'],
    affects: { sectors: ['Technology', 'Financials'], symbols: ['MSFT'], topics: ['Automated Decisions', 'Liability'] },
    impact: 'For a decade this was the controlling standard: plaintiffs had to reverse-engineer an internal deviation to recover, which in practice shielded operators that kept only summary documentation.',
    citations: [],
    supersededBy: 'd-calder',
    effectiveDate: '2024-03-11T00:00:00-04:00',
    provenanceHash: 'sha256:meridian…a11', redline: [
      { type: 'ctx', text: 'Holding — standard of liability.' },
      { type: 'add', text: '  Liability attaches only on proof of departure from a documented internal standard.' },
    ],
  },
  {
    id: 'd-doe', cite: 'Doe v. Data Authority', title: 'Doe v. Data Authority', type: 'case', jurisdiction: 'Federal', status: 'enacted', updated: '2025-06-20T10:00:00-04:00',
    summary: 'Distinguished Meridian on its facts: where no internal standard exists at all, the documented-deviation test cannot apply and the operator must show its process was reasonable.',
    agency: 'District Court (S.D.N.Y.)',
    tags: ['automated-decisions', 'liability', 'distinguished'],
    affects: { sectors: ['Technology'], symbols: ['GOOGL'], topics: ['Automated Decisions'] },
    impact: 'Carved out the "no-standard" case from Meridian without disturbing it — the first crack, narrowing where operators could hide behind the absence of documentation.',
    citations: [{ cite: 'Meridian Logistics v. State', title: 'Meridian Logistics v. State', docketId: 'd-meridian' }],
    effectiveDate: '2025-06-20T00:00:00-04:00',
    provenanceHash: 'sha256:doe…b20', redline: [
      { type: 'ctx', text: 'Holding — scope of Meridian.' },
      { type: 'add', text: '  Where no internal standard exists, the operator must affirmatively show a reasonable process.' },
    ],
  },
  {
    id: 'd-calder', cite: 'Calder v. Meridian Logistics', title: 'Calder v. Meridian Logistics', type: 'case', jurisdiction: 'Federal', status: 'enacted', updated: '2026-06-15T10:00:00-04:00',
    summary: 'Overruled Meridian: an operator that cannot produce a replayable record of a challenged automated decision is presumed at fault, aligning the common-law standard with the DIR-2026-ASL evidence regime.',
    agency: 'Supreme Court',
    tags: ['automated-decisions', 'liability', 'overruled', 'audit-trail'],
    affects: { sectors: ['Technology', 'Financials', 'Healthcare'], symbols: ['MSFT', 'JPM'], topics: ['Automated Decisions', 'Liability'] },
    impact: 'Flips the decade-old default: the burden now sits with the operator, and "we only kept summaries" is no longer a defense. Every firm relying on Meridian must revisit its retention posture.',
    citations: [{ cite: 'Meridian Logistics v. State', title: 'Meridian Logistics v. State', docketId: 'd-meridian' }],
    effectiveDate: '2026-06-15T00:00:00-04:00',
    provenanceHash: 'sha256:calder…c15', redline: [
      { type: 'ctx', text: 'Holding — overruling Meridian.' },
      { type: 'del', text: '  Liability attaches only on proof of departure from a documented internal standard.' },
      { type: 'add', text: '  Absent a replayable record, fault is presumed and the burden shifts to the operator.' },
    ],
  },
];

export const asOf = '2026-07-03T14:00:00-04:00';
