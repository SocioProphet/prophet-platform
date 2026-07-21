// Anatomy atlas manifest — maps each organ system to a POLISHED, OPEN-LICENSED medical illustration
// (not hand-drawn SVG). Sources are CC-BY so the estate can self-host + attribute cleanly:
//   • OpenStax Anatomy & Physiology 2e — CC BY 4.0 (textbook-quality system plates)
//   • Servier Medical Art (SMART)       — CC BY 4.0 (physiology + organ art)
// mirrored/browsable per-figure on AnatomyTOOL (Leiden University), which labels each image's license.
//
// Each plate resolves in order: a VENDORED local asset (sovereign, preferred) → a REMOTE CC-BY source
// (Wikimedia Commons Special:FilePath, for immediate review) → a graceful placeholder. Vendoring the
// approved images into public/atlas/systems/ is the follow-up; the surface works either way.
//
// license compliance: every rendered plate shows its attribution; see CREDIT below for the blanket line.

export interface AtlasPlate {
  title: string;
  vendored: string;          // sovereign local path (served from public/); populated when vendored
  remote: string;            // CC-BY remote (Commons Special:FilePath) for immediate review; '' if unconfirmed
  source: string;            // human-readable source
  sourceUrl: string;         // browse/review + confirm the exact figure
  license: string;
  attribution: string;
}

const commons = (file: string) => `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}`;

// keyed on the health-twin service's system ids (nervous, cardiovascular, respiratory, hepatic, urinary)
export const ATLAS: Record<string, AtlasPlate> = {
  nervous: {
    title: 'Nervous system',
    vendored: 'atlas/systems/nervous.png', remote: '',
    source: 'OpenStax Anatomy & Physiology 2e',
    sourceUrl: 'https://anatomytool.org/search?query=openstax%20nervous%20system',
    license: 'CC BY 4.0', attribution: 'OpenStax Anatomy & Physiology 2e, CC BY 4.0',
  },
  cardiovascular: {
    title: 'Cardiovascular system',
    vendored: 'atlas/systems/cardiovascular.png', remote: '',
    source: 'OpenStax Anatomy & Physiology 2e',
    sourceUrl: 'https://anatomytool.org/search?query=openstax%20cardiovascular%20heart',
    license: 'CC BY 4.0', attribution: 'OpenStax Anatomy & Physiology 2e, CC BY 4.0',
  },
  respiratory: {
    title: 'Respiratory system',
    vendored: 'atlas/systems/respiratory.png',
    remote: commons('2301 Major Respiratory Organs.jpg'),
    source: 'OpenStax A&P 2e — fig. 22.2 “Major Respiratory Organs”',
    sourceUrl: 'https://anatomytool.org/content/openstax-anatphys-fig222-major-respiratory-organs-english-labels',
    license: 'CC BY 4.0', attribution: 'OpenStax Anatomy & Physiology 2e (fig. 22.2), CC BY 4.0',
  },
  hepatic: {
    title: 'Digestive system',
    vendored: 'atlas/systems/digestive.png', remote: '',
    source: 'OpenStax Anatomy & Physiology 2e',
    sourceUrl: 'https://anatomytool.org/search?query=openstax%20digestive%20system',
    license: 'CC BY 4.0', attribution: 'OpenStax Anatomy & Physiology 2e, CC BY 4.0',
  },
  urinary: {
    title: 'Urinary system',
    vendored: 'atlas/systems/urinary.png', remote: '',
    source: 'OpenStax Anatomy & Physiology 2e',
    sourceUrl: 'https://anatomytool.org/search?query=openstax%20urinary%20system',
    license: 'CC BY 4.0', attribution: 'OpenStax Anatomy & Physiology 2e, CC BY 4.0',
  },
};

// blanket credit line for the surface footer
export const ATLAS_CREDIT = 'Illustrations: OpenStax Anatomy & Physiology 2e and Servier Medical Art — CC BY 4.0.';

export function plateFor(systemId: string): AtlasPlate | undefined { return ATLAS[systemId]; }
