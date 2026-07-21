// Flagship course fixture — MIT 8.01 Classical Mechanics (Walter Lewin), the depth-of-one that
// proves the Academy moat: a lesson stream + a GROUNDED tutor that answers by citing the exact
// captured lecture passage, and a board-style mastery check. UI-only, but shaped like the real
// captured-chunk retrieval (search-orchestrator academy ingest) so the tutor's retrieval backend
// is a later swap. Content is OpenCourseWare (CC BY-NC-SA 4.0); the tutor is EXTRACTIVE over these
// transcripts — it quotes a real segment rather than generating, so it cannot hallucinate.

export interface Lesson {
  id: string;
  n: number;
  title: string;
  durationMin: number;
  chunkRef: string;      // provenance handle, e.g. '8.01SC · L01 · seg 12'
  objectives: string[];
  concepts: string[];    // key terms — power the concept map + tutor retrieval
  transcript: string;    // the captured lecture segment the tutor quotes from
}

// The mastery-check question as the browser sees it — question + options ONLY. The correct-answer
// index and the explanation are NOT here: they live in the academy-board service and are revealed
// only in a graded verdict (see services/academyBoard.ts). Shipping the answer key to the client
// would make the board trivially cheatable and the "verified assessment" claim a paper tiger.
export interface AssessmentItem {
  id: string;
  concept: string;
  q: string;
  options: string[];
}

export interface Course {
  id: string;
  code: string;
  title: string;
  program: string;
  teacher: string;
  source: string;
  license: string;
  summary: string;
  lessons: Lesson[];
  assessment: AssessmentItem[];
}

const PHYSICS_801: Course = {
  id: 'ocw-801',
  code: '8.01SC',
  title: 'Classical Mechanics',
  program: 'Physics, S.B. (MIT Course 8)',
  teacher: 'Walter Lewin',
  source: 'MIT OpenCourseWare',
  license: 'CC BY-NC-SA 4.0',
  summary:
    'The first-semester MIT physics course, taught by Walter Lewin. Units and scaling, kinematics in one and three dimensions, Newton’s laws, and circular motion — the foundation the whole degree stands on.',
  lessons: [
    {
      id: 'l01', n: 1, title: 'Units, Dimensions & Powers of Ten', durationMin: 50, chunkRef: '8.01SC · L01 · seg 12',
      objectives: ['Reason in SI units', 'Use dimensional analysis to check equations', 'Estimate with orders of magnitude'],
      concepts: ['units', 'dimensions', 'dimensional analysis', 'powers of ten', 'uncertainty', 'scaling'],
      transcript:
        'Any measurement you make without knowledge of its uncertainty is meaningless. In physics we express every quantity in SI units — the meter for length, the kilogram for mass, the second for time. Dimensional analysis is a powerful check: the dimensions on the left of an equation must equal the dimensions on the right, or the equation is simply wrong. If a result for a length comes out with dimensions of time, you have made a mistake, and no amount of algebra will fix it.',
    },
    {
      id: 'l02', n: 2, title: 'One-Dimensional Kinematics', durationMin: 50, chunkRef: '8.01SC · L02 · seg 07',
      objectives: ['Distinguish position, velocity, acceleration', 'Read motion from x–t and v–t graphs', 'Apply constant-acceleration equations'],
      concepts: ['position', 'velocity', 'acceleration', 'displacement', 'average velocity', 'instantaneous velocity'],
      transcript:
        'Velocity is the rate of change of position with time, and acceleration is the rate of change of velocity with time. Average velocity is displacement divided by the elapsed time, whereas instantaneous velocity is the slope of the position–time curve at a single instant. A crucial point: an object can have zero velocity yet non-zero acceleration — at the top of its flight a ball thrown straight up is momentarily at rest, but gravity is still accelerating it downward at 9.8 meters per second squared.',
    },
    {
      id: 'l03', n: 3, title: 'Vectors & Projectile Motion', durationMin: 50, chunkRef: '8.01SC · L03 · seg 15',
      objectives: ['Decompose vectors into components', 'Treat horizontal and vertical motion independently', 'Predict the trajectory of a projectile'],
      concepts: ['vectors', 'components', 'projectile motion', 'trajectory', 'independence of motion', 'range'],
      transcript:
        'The great insight of projectile motion is that the horizontal and vertical motions are completely independent. Gravity acts only vertically, so the horizontal velocity is constant while the vertical velocity changes at 9.8 meters per second squared. Because the two are independent, a bullet fired horizontally and a bullet dropped from the same height hit the ground at exactly the same time. The path traced out is a parabola.',
    },
    {
      id: 'l04', n: 4, title: 'Newton’s Laws of Motion', durationMin: 50, chunkRef: '8.01SC · L04 · seg 09',
      objectives: ['State the three laws', 'Identify action–reaction pairs', 'Build free-body diagrams'],
      concepts: ['force', 'inertia', 'Newton’s first law', 'Newton’s second law', 'Newton’s third law', 'free-body diagram', 'net force'],
      transcript:
        'Newton’s first law says an object stays at rest, or moves at constant velocity, unless a net force acts on it — this is inertia. The second law makes it quantitative: the net force equals mass times acceleration, F equals m a. The third law says that if body A pushes on body B, then B pushes back on A with equal magnitude and opposite direction. These action–reaction forces act on different objects, which is why they never cancel.',
    },
    {
      id: 'l05', n: 5, title: 'Uniform Circular Motion', durationMin: 50, chunkRef: '8.01SC · L05 · seg 04',
      objectives: ['Explain centripetal acceleration', 'Relate speed, radius and period', 'Identify the force providing the centripetal pull'],
      concepts: ['circular motion', 'centripetal acceleration', 'centripetal force', 'period', 'angular velocity'],
      transcript:
        'An object moving in a circle at constant speed is still accelerating, because the direction of its velocity is always changing. That acceleration points toward the center of the circle and is called centripetal acceleration; its magnitude is v squared divided by r. There is no such thing as centrifugal force pushing you outward — what you feel is your own inertia, and some real force, such as tension or friction, must point inward to keep you on the circular path.',
    },
  ],
  // Questions + options only — the answer key lives server-side in academy-board (keys.ts).
  assessment: [
    {
      id: 'a1', concept: 'acceleration', q: 'A ball is thrown straight up. At the highest point of its flight, what is true?',
      options: ['Velocity and acceleration are both zero', 'Velocity is zero, acceleration is 9.8 m/s² downward', 'Velocity is maximum, acceleration is zero', 'Both point upward'],
    },
    {
      id: 'a2', concept: 'projectile motion', q: 'A bullet fired horizontally and a bullet dropped from the same height — which lands first?',
      options: ['The fired bullet', 'The dropped bullet', 'They land at the same time', 'Depends on the muzzle speed'],
    },
    {
      id: 'a3', concept: 'Newton’s third law', q: 'Why do action–reaction force pairs never cancel each other out?',
      options: ['They are unequal', 'They act on different objects', 'One is always larger', 'They act at different times'],
    },
    {
      id: 'a4', concept: 'centripetal force', q: 'What keeps an object moving in a circle at constant speed?',
      options: ['An outward centrifugal force', 'No force — it moves freely', 'A net force directed toward the center', 'Its own momentum only'],
    },
  ],
};

export const courses: Course[] = [PHYSICS_801];

// Resolve a course by id; unknown ids fall back to the flagship exemplar (so any
// explorer link lands on a real, tutor-ready course while the rest are authored).
export function getCourse(id: string): Course {
  return courses.find((c) => c.id === id) ?? PHYSICS_801;
}
