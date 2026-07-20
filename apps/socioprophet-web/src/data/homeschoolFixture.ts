// Homeschool planner fixture (/academy/homeschool). Standards-based (NGSS + Common Core), the K-12
// analog of the university registrar: Grade band → Subject → Standard → captured resource → Skill.
// UI-only, shaped so a real standards corpus (CK-12 / OpenStax / NGSS·CCSS public standards) can swap
// in later. CC-open sources only. A parent builds a plan against the standards and tracks coverage.

export interface ResourceRef {
  title: string;
  source: string;   // 'CK-12' | 'OpenStax' | 'NGSS' | 'Common Core'
  license: string;
  captured: boolean;
}
export interface Standard {
  code: string;         // 'MS-PS1-1', 'CCSS.MATH.6.RP.A.1', …
  title: string;
  description: string;
  resources: ResourceRef[];
  skills: string[];
}
export interface SubjectStrand {
  subject: string;
  framework: string;    // 'NGSS' | 'Common Core'
  standards: Standard[];
}
export interface GradeProgram {
  band: string;         // 'K-5' | '6-8' | '9-12'
  label: string;
  subjects: SubjectStrand[];
}

const CK12 = (title: string, captured = true): ResourceRef => ({ title, source: 'CK-12', license: 'CC BY-NC 3.0', captured });
const OSTAX = (title: string, captured = true): ResourceRef => ({ title, source: 'OpenStax', license: 'CC BY 4.0', captured });

export const gradePrograms: GradeProgram[] = [
  {
    band: 'K-5', label: 'Elementary (K–5)',
    subjects: [
      {
        subject: 'Science', framework: 'NGSS',
        standards: [
          { code: '3-LS1-1', title: 'Life cycles', description: 'Develop models to describe that organisms have unique and diverse life cycles.', resources: [CK12('CK-12 Life Science: Life Cycles')], skills: ['sk-inquiry', 'sk-modeling'] },
          { code: '4-PS3-2', title: 'Energy transfer', description: 'Observe energy being transferred from place to place by sound, light, heat, and electric currents.', resources: [CK12('CK-12 Physical Science: Energy')], skills: ['sk-inquiry'] },
          { code: '5-ESS1-1', title: 'Stars & brightness', description: 'Support an argument that differences in apparent brightness of the sun vs. other stars is due to their relative distances.', resources: [CK12('CK-12 Earth Science: Stars', false)], skills: ['sk-argument', 'sk-modeling'] },
        ],
      },
      {
        subject: 'Mathematics', framework: 'Common Core',
        standards: [
          { code: '3.OA.A.1', title: 'Interpret products', description: 'Interpret products of whole numbers (e.g., 5 × 7 as 5 groups of 7).', resources: [OSTAX('OpenStax Prealgebra: Multiplication')], skills: ['sk-algebra'] },
          { code: '4.NF.A.1', title: 'Equivalent fractions', description: 'Explain why a fraction a/b is equivalent to (n×a)/(n×b).', resources: [OSTAX('OpenStax Prealgebra: Fractions')], skills: ['sk-algebra'] },
          { code: '5.NBT.A.3', title: 'Read & write decimals', description: 'Read, write, and compare decimals to thousandths.', resources: [OSTAX('OpenStax Prealgebra: Decimals')], skills: ['sk-data'] },
        ],
      },
      {
        subject: 'English/Language Arts', framework: 'Common Core',
        standards: [
          { code: 'RL.3.1', title: 'Ask & answer questions', description: 'Ask and answer questions to demonstrate understanding of a text, referring explicitly to the text.', resources: [CK12('CK-12 Reading: Comprehension', false)], skills: ['sk-argument', 'sk-writing'] },
          { code: 'W.4.1', title: 'Opinion writing', description: 'Write opinion pieces supporting a point of view with reasons and information.', resources: [CK12('CK-12 Writing: Opinion', false)], skills: ['sk-writing', 'sk-argument'] },
        ],
      },
    ],
  },
  {
    band: '6-8', label: 'Middle School (6–8)',
    subjects: [
      {
        subject: 'Science', framework: 'NGSS',
        standards: [
          { code: 'MS-PS1-1', title: 'Structure of matter', description: 'Develop models to describe the atomic composition of simple molecules and extended structures.', resources: [CK12('CK-12 Physical Science: Matter'), OSTAX('OpenStax Chemistry: Atoms First (intro)')], skills: ['sk-modeling', 'sk-inquiry'] },
          { code: 'MS-LS1-1', title: 'Cells as the unit of life', description: 'Conduct an investigation to provide evidence that living things are made of cells.', resources: [CK12('CK-12 Life Science: Cells')], skills: ['sk-inquiry', 'sk-argument'] },
          { code: 'MS-ESS1-1', title: 'Earth–sun–moon system', description: 'Develop and use a model of the Earth-sun-moon system to explain cyclic patterns of eclipses and seasons.', resources: [CK12('CK-12 Earth Science: Astronomy')], skills: ['sk-modeling', 'sk-data'] },
          { code: 'MS-ETS1-1', title: 'Engineering design', description: 'Define the criteria and constraints of a design problem with precision.', resources: [{ title: 'NGSS ETS1 (standard)', source: 'NGSS', license: 'Public standard', captured: false }], skills: ['sk-modeling', 'sk-argument'] },
        ],
      },
      {
        subject: 'Mathematics', framework: 'Common Core',
        standards: [
          { code: '6.RP.A.1', title: 'Ratios', description: 'Understand the concept of a ratio and use ratio language to describe a relationship.', resources: [OSTAX('OpenStax Prealgebra: Ratios')], skills: ['sk-algebra', 'sk-data'] },
          { code: '7.EE.B.4', title: 'Equations & inequalities', description: 'Use variables to represent quantities and construct simple equations and inequalities to solve problems.', resources: [OSTAX('OpenStax Elementary Algebra: Equations')], skills: ['sk-algebra'] },
          { code: '8.F.A.1', title: 'Functions', description: 'Understand that a function assigns to each input exactly one output.', resources: [OSTAX('OpenStax Elementary Algebra: Functions')], skills: ['sk-algebra'] },
        ],
      },
      {
        subject: 'English/Language Arts', framework: 'Common Core',
        standards: [
          { code: 'RI.7.1', title: 'Cite textual evidence', description: 'Cite several pieces of textual evidence to support analysis of what the text says explicitly and inferentially.', resources: [CK12('CK-12 Reading: Informational Text', false)], skills: ['sk-argument', 'sk-writing'] },
          { code: 'W.8.1', title: 'Argumentative writing', description: 'Write arguments to support claims with clear reasons and relevant evidence.', resources: [CK12('CK-12 Writing: Argument', false)], skills: ['sk-writing', 'sk-argument'] },
        ],
      },
    ],
  },
  {
    band: '9-12', label: 'High School (9–12)',
    subjects: [
      {
        subject: 'Science', framework: 'NGSS',
        standards: [
          { code: 'HS-PS2-1', title: "Newton's second law", description: "Analyze data to support the claim that Newton's second law of motion describes the relationship among force, mass, and acceleration.", resources: [OSTAX('OpenStax College Physics: Dynamics'), { title: 'MIT 8.01 (bridge to university)', source: 'MIT OCW', license: 'CC BY-NC-SA 4.0', captured: true }], skills: ['sk-mechanics', 'sk-data'] },
          { code: 'HS-LS1-2', title: 'Systems in organisms', description: 'Develop and use a model to illustrate the hierarchical organization of interacting systems in multicellular organisms.', resources: [OSTAX('OpenStax Biology: Systems')], skills: ['sk-modeling', 'sk-inquiry'] },
        ],
      },
      {
        subject: 'Mathematics', framework: 'Common Core',
        standards: [
          { code: 'A-REI.B.4', title: 'Quadratic equations', description: 'Solve quadratic equations in one variable by inspection, completing the square, the quadratic formula, and factoring.', resources: [OSTAX('OpenStax Intermediate Algebra: Quadratics')], skills: ['sk-algebra'] },
          { code: 'F-IF.C.7', title: 'Graphing functions', description: 'Graph functions expressed symbolically and show key features of the graph.', resources: [OSTAX('OpenStax Precalculus: Functions')], skills: ['sk-algebra', 'sk-calculus'] },
        ],
      },
    ],
  },
];

export function coverageOfSubject(s: SubjectStrand): { captured: number; total: number; pct: number } {
  const total = s.standards.length;
  const captured = s.standards.filter((st) => st.resources.some((r) => r.captured)).length;
  return { captured, total, pct: total ? Math.round((captured / total) * 100) : 0 };
}
