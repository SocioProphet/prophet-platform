// Alexandrian Academy — fixture for the education section (/academy/*). UI-only, but shaped to
// MIRROR the real registrar/capture backend (~/dev/alexandrian-academy → scripts/build-registrar.py
// → academy/registrar-<program>.json, and the search-orchestrator academy ingest), so wiring the
// live services later is a swap of the loader, not a rewrite of the surface.
//
// The model is ONE structure across the whole ladder — Program → Requirement → Course → Skill —
// so the same explorer renders a K-12 homeschool path (NGSS/Common Core strands) and an MIT degree
// (credit-unit requirements) identically. Skills are shared nodes: one algebra skill serves physics,
// econ, and CS — the graph-native curriculum that's the moat over a flat course catalog.
//
// LICENSING: only CC-open sources enter the commons (MIT OCW, OpenStax, CK-12, NGSS/Common Core are
// public standards). edX/Coursera/ARR content is deliberately absent — see the academy governance rules.

export type LadderLevel = 'k12' | 'undergrad' | 'grad' | 'professional';

export interface Skill { id: string; name: string }

export interface CourseRef {
  id: string;
  code: string;
  title: string;
  source: string;      // 'MIT OCW' | 'OpenStax' | 'CK-12' | 'NGSS'
  license: string;     // e.g. 'CC BY-NC-SA 4.0'
  captured: boolean;   // is the content actually in the Knowledge Commons?
  chunks?: number;     // captured depth (retrieval chunks)
  units?: number;      // credit-units (university)
  teacher?: string;    // persona the tutor embodies
  skills: string[];    // Skill ids this course develops
}

export interface Requirement {
  id: string;
  title: string;
  code?: string;       // standard code (NGSS 'MS-PS1') or requirement code (university)
  units?: number;      // required credit-units (university)
  courses: CourseRef[];
  satisfied: boolean;  // is the requirement covered by captured content?
}

export interface Program {
  id: string;
  level: LadderLevel;
  title: string;
  credential: string;  // 'S.B.' | 'Homeschool path' | 'Certificate'
  framework: string;   // 'MIT Course 8' | 'NGSS + Common Core' | …
  institution: string;
  teacher: string;     // headline persona
  summary: string;
  requiredUnits?: number;  // university coverage math
  requirements: Requirement[];
}

// ── Shared skill nodes (reused across programs — the graph-native curriculum) ──
export const skills: Skill[] = [
  { id: 'sk-algebra', name: 'Algebraic reasoning' },
  { id: 'sk-calculus', name: 'Calculus' },
  { id: 'sk-linalg', name: 'Linear algebra' },
  { id: 'sk-mechanics', name: 'Classical mechanics' },
  { id: 'sk-em', name: 'Electromagnetism' },
  { id: 'sk-modeling', name: 'Scientific modeling' },
  { id: 'sk-inquiry', name: 'Scientific inquiry' },
  { id: 'sk-argument', name: 'Evidence-based argument' },
  { id: 'sk-data', name: 'Data & statistics' },
  { id: 'sk-writing', name: 'Expository writing' },
];

// ── Programs ────────────────────────────────────────────────────────────────
export const programs: Program[] = [
  // K-12 homeschool path (audience #1) — standards-based, NGSS + Common Core.
  {
    id: 'k12-ms-science',
    level: 'k12',
    title: 'Middle School Science',
    credential: 'Homeschool path',
    framework: 'NGSS (grades 6–8)',
    institution: 'Alexandrian Academy · Knowledge Commons',
    teacher: 'Bill Nye (science communication)',
    summary:
      'A standards-aligned homeschool science path for grades 6–8, mapped onto the Next Generation Science Standards. Each strand traces to captured, openly-licensed content (CK-12, OpenStax) and the skills it builds — so a parent can see coverage and gaps at a glance.',
    requirements: [
      {
        id: 'k12-ps', title: 'Matter & Its Interactions', code: 'MS-PS1', satisfied: true,
        courses: [
          { id: 'ck12-ps-matter', code: 'CK-12 PS', title: 'Physical Science: Matter', source: 'CK-12', license: 'CC BY-NC 3.0', captured: true, chunks: 640, teacher: 'Bill Nye', skills: ['sk-modeling', 'sk-inquiry'] },
          { id: 'ostax-chem', code: 'OSTAX', title: 'Chemistry: Atoms First (intro units)', source: 'OpenStax', license: 'CC BY 4.0', captured: true, chunks: 410, skills: ['sk-modeling', 'sk-data'] },
        ],
      },
      {
        id: 'k12-ls', title: 'From Molecules to Organisms', code: 'MS-LS1', satisfied: true,
        courses: [
          { id: 'ck12-life', code: 'CK-12 LS', title: 'Life Science', source: 'CK-12', license: 'CC BY-NC 3.0', captured: true, chunks: 720, teacher: 'Bill Nye', skills: ['sk-inquiry', 'sk-argument'] },
        ],
      },
      {
        id: 'k12-ess', title: 'Earth & Space Sciences', code: 'MS-ESS1', satisfied: true,
        courses: [
          { id: 'ck12-earth', code: 'CK-12 ESS', title: 'Earth Science', source: 'CK-12', license: 'CC BY-NC 3.0', captured: true, chunks: 560, skills: ['sk-modeling', 'sk-data'] },
        ],
      },
      {
        id: 'k12-eng', title: 'Engineering Design', code: 'MS-ETS1', satisfied: false,
        courses: [
          { id: 'ngss-ets', code: 'NGSS ETS1', title: 'Engineering Design (standard)', source: 'NGSS', license: 'Public standard', captured: false, skills: ['sk-modeling', 'sk-argument'] },
        ],
      },
      {
        id: 'k12-math', title: 'Grade-level Mathematics', code: 'CCSS.MATH 6–8', satisfied: true,
        courses: [
          { id: 'ostax-prealg', code: 'OSTAX', title: 'Prealgebra', source: 'OpenStax', license: 'CC BY 4.0', captured: true, chunks: 880, skills: ['sk-algebra', 'sk-data'] },
        ],
      },
    ],
  },

  // University degree (audience #2) — the real MIT Physics S.B., degree-back-into, 93% captured.
  {
    id: 'mit-physics-sb',
    level: 'undergrad',
    title: 'Physics, S.B.',
    credential: 'S.B. (Bachelor of Science)',
    framework: 'MIT Course 8',
    institution: 'Massachusetts Institute of Technology · OCW',
    teacher: 'Walter Lewin (8.01/8.02)',
    summary:
      'The MIT Course 8 Physics degree, backed into from the catalogue onto captured OpenCourseWare. 14 of 15 required subjects (168/180 units, 93%) are already teachable from the Commons — the only gap is the student’s own thesis. Anchored on Walter Lewin’s 8.01/8.02.',
    requiredUnits: 180,
    requirements: [
      {
        id: 'p-mech', title: 'Classical Mechanics (8.01)', code: '8.01', units: 12, satisfied: true,
        courses: [{ id: 'ocw-801', code: '8.01SC', title: 'Classical Mechanics', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true, chunks: 4781, units: 12, teacher: 'Walter Lewin', skills: ['sk-mechanics', 'sk-calculus'] }],
      },
      {
        id: 'p-em', title: 'Electricity & Magnetism (8.02)', code: '8.02', units: 12, satisfied: true,
        courses: [{ id: 'ocw-802', code: '8.02', title: 'Electricity & Magnetism', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true, chunks: 3120, units: 12, teacher: 'Walter Lewin', skills: ['sk-em', 'sk-calculus'] }],
      },
      {
        id: 'p-linalg', title: 'Linear Algebra (18.06)', code: '18.06', units: 12, satisfied: true,
        courses: [{ id: 'ocw-1806', code: '18.06', title: 'Linear Algebra', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true, chunks: 2960, units: 12, teacher: 'Gilbert Strang', skills: ['sk-linalg', 'sk-algebra'] }],
      },
      {
        id: 'p-calc', title: 'Multivariable Calculus (18.02)', code: '18.02', units: 12, satisfied: true,
        courses: [{ id: 'ocw-1802', code: '18.02', title: 'Multivariable Calculus', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true, chunks: 2540, units: 12, skills: ['sk-calculus'] }],
      },
      {
        id: 'p-quantum', title: 'Quantum Physics (8.04)', code: '8.04', units: 12, satisfied: true,
        courses: [{ id: 'ocw-804', code: '8.04', title: 'Quantum Physics I', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true, chunks: 2210, units: 12, skills: ['sk-mechanics', 'sk-calculus'] }],
      },
      {
        id: 'p-thesis', title: 'Senior Thesis (8.THU)', code: '8.THU', units: 12, satisfied: false,
        courses: [{ id: 'thesis', code: '8.THU', title: 'Undergraduate Thesis', source: 'MIT OCW', license: '—', captured: false, units: 12, skills: ['sk-writing', 'sk-argument'] }],
      },
    ],
  },
];

// ── Derived helpers (mirror the registrar's coverage math) ────────────────────
export function coverageOf(p: Program): { satisfied: number; total: number; pct: number; units?: number; requiredUnits?: number } {
  const total = p.requirements.length;
  const satisfied = p.requirements.filter((r) => r.satisfied).length;
  const units = p.requirements.filter((r) => r.satisfied).reduce((s, r) => s + (r.units ?? 0), 0);
  const pct = p.requiredUnits
    ? Math.round((units / p.requiredUnits) * 100)
    : Math.round((satisfied / Math.max(1, total)) * 100);
  return { satisfied, total, pct, units: p.requiredUnits ? units : undefined, requiredUnits: p.requiredUnits };
}

export function capturedChunks(p: Program): number {
  return p.requirements.reduce((s, r) => s + r.courses.reduce((c, x) => c + (x.chunks ?? 0), 0), 0);
}

export function skillName(id: string): string {
  return skills.find((s) => s.id === id)?.name ?? id;
}

// Skills that appear in more than one program — the reuse that makes it a graph, not a catalog.
export function sharedSkills(): { id: string; name: string; programs: string[] }[] {
  const byskill = new Map<string, Set<string>>();
  for (const p of programs)
    for (const r of p.requirements)
      for (const c of r.courses)
        for (const sk of c.skills) {
          if (!byskill.has(sk)) byskill.set(sk, new Set());
          byskill.get(sk)!.add(p.id);
        }
  return [...byskill.entries()]
    .filter(([, ps]) => ps.size > 1)
    .map(([id, ps]) => ({ id, name: skillName(id), programs: [...ps] }));
}

export const LADDER: { level: LadderLevel; label: string; blurb: string }[] = [
  { level: 'k12', label: 'K-12 · Homeschool', blurb: 'Standards-based paths (NGSS, Common Core)' },
  { level: 'undergrad', label: 'Undergraduate', blurb: 'Degree-back-into the university catalogue' },
  { level: 'grad', label: 'Graduate', blurb: 'Research-depth subjects & seminars' },
  { level: 'professional', label: 'Professional', blurb: 'Skill-graph micro-credentials' },
];
