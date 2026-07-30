

// ── #942 follow-up: id-collision fix ──────────────────────────────────────

test('openConsult mints unique ids even when N calls hit the same ms + scope', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '100' });
  // Tight loop: many calls will land in the same millisecond, and the scope is
  // fixed. Pre-fix, all but one collided and silently overwrote each other.
  const ids = new Set<string>();
  for (let i = 0; i < 50; i++) {
    const r = m.openConsult({ patient: 'p' }, 'shared-scope', 'standard', true);
    if (r.consult_id) ids.add(r.consult_id);
  }
  assert.equal(ids.size, 50, 'every open must produce a unique id even under contention');
  assert.equal(m.consultCount(), 50, 'the ledger must hold every consult, not overwrite');
});

test('submitOpinion mints unique opinion ids in a tight loop', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [id] = agree(m, 1);
  const opIds = new Set<string>();
  for (let i = 0; i < 20; i++) {
    const op = m.submitOpinion(id!, 'reviewer-x', 'assessment-x', 'moderate');
    if ('id' in op) opIds.add(op.id);
  }
  assert.equal(opIds.size, 20, 'every opinion id must be unique');
});

test('requestMore mints unique request ids in a tight loop', async () => {
  const m = await freshModule({ HEALTH_TWIN_CONSULT_MAX: '10' });
  const [id] = agree(m, 1);
  const rIds = new Set<string>();
  for (let i = 0; i < 20; i++) {
    const r = m.requestMore(id!, 'labs.a1c', 'need it');
    if ('id' in r) rIds.add(r.id);
  }
  assert.equal(rIds.size, 20, 'every more-request id must be unique');
});
