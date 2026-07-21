// Server-side answer key for the Academy mastery check. This is the whole point of the
// service: the correct-answer index and explanation live HERE, never in the browser bundle,
// so the "board engine" is a real authority a client cannot read or forge. Each item is
// GROUNDED — it carries the captured-lecture chunkRef the mastery is measured against, so a
// verdict cites the same OpenCourseWare segment the tutor quotes from.
//
// Seeded from MIT 8.01 Classical Mechanics (Walter Lewin, OCW CC BY-NC-SA 4.0). Adding a
// course is data-only: a new courseId block.

export interface KeyItem {
  answer: number;   // index into the options the client renders
  explain: string;  // shown only AFTER a pick, returned by the grade response
  concept: string;
  chunkRef: string; // captured-lecture provenance the item is grounded in
}

export type CourseKey = Record<string, KeyItem>;

export const ANSWER_KEY: Record<string, CourseKey> = {
  'ocw-801': {
    a1: {
      answer: 1, concept: 'acceleration', chunkRef: '8.01SC · L02 · seg 07',
      explain: 'At the top the ball is momentarily at rest (v = 0) but gravity never stops — acceleration is 9.8 m/s² downward throughout (Lecture 2).',
    },
    a2: {
      answer: 2, concept: 'projectile motion', chunkRef: '8.01SC · L03 · seg 15',
      explain: 'Horizontal and vertical motion are independent; both have the same vertical drop under gravity, so they land together (Lecture 3).',
    },
    a3: {
      answer: 1, concept: 'Newton’s third law', chunkRef: '8.01SC · L04 · seg 09',
      explain: 'Newton’s third-law pairs are equal and opposite but act on different bodies, so they can’t cancel on a single object (Lecture 4).',
    },
    a4: {
      answer: 2, concept: 'centripetal force', chunkRef: '8.01SC · L05 · seg 04',
      explain: 'A centripetal (center-pointing) net force is required; “centrifugal force” is just felt inertia, not a real inward force (Lecture 5).',
    },
  },
};
