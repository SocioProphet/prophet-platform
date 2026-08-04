// The cockpit revendor (#1428) restored DevSecOpsWorkroomReportCard.vue, TritFabricReadinessLabels.vue
// and WorkstationDevSecOps.vue byte-for-byte (#1432), but never carried forward main.ts's import and
// route registration for WorkstationDevSecOps — CI's own validators only inspect the .vue files'
// content, never main.ts, so a page with no route pointing at it passed CI silently. Read main.ts as
// text (not a router harness) so this proves the file the build actually ships, not a fixture written
// to agree with the assertion.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const MAIN_TS = readFileSync(resolve(HERE, '../main.ts'), 'utf-8');

describe('WorkstationDevSecOps is actually reachable', () => {
  it('main.ts imports the page component', () => {
    expect(MAIN_TS).toMatch(/import\s+WorkstationDevSecOps\s+from\s+['"]\.\/pages\/WorkstationDevSecOps\.vue['"]/);
  });

  it('main.ts registers a route to it', () => {
    expect(MAIN_TS).toMatch(/path:\s*['"]\/workstation\/devsecops['"],\s*component:\s*WorkstationDevSecOps/);
  });
});
