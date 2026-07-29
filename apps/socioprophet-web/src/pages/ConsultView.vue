<script setup lang="ts">
// Blinded second opinions (wall 4) — the moat, in the cockpit. Consent-scoped, double-blind,
// non-diagnostic. Three roles over ONE live consult: the Patient (agrees, then reads the result), the
// Doctor (a blinded record + one independent read), the Coordinator (tracks who reviewed). Wired to the
// health-twin engine's /api/health/consult* endpoints — the aggregate is the real concordance signal.
import { ref, computed, onMounted } from 'vue';
import { openConsult, consultResult, reviewerSlice, submitOpinion, type DeidView, type ConsultAgg } from '../services/healthTwinApi';

type Role = 'patient' | 'doctor' | 'coord';
const role = ref<Role>('patient');
const accepted = ref(false); // the checkbox — patient ticks the terms
const agreed = ref(false);   // true once the consult has actually opened
const consultId = ref('');
const slice = ref<DeidView | null>(null);
const agg = ref<ConsultAgg | null>(null);
const busy = ref(false);
const err = ref('');

// The patient's agreement is the gate — nothing opens until they accept the terms.
async function agree() {
  // The checkbox only disabled a button. Its value was never sent, so the gate held in
  // the UI and nowhere else — any direct call to the API opened a consult without it.
  // Send what the patient actually ticked, and refuse locally as well.
  if (!accepted.value) { err.value = 'agreement is required before a consult can open'; return; }
  busy.value = true; err.value = '';
  try {
    const r = await openConsult('Cardiovascular', 'standard', accepted.value);
    if (r.error || !r.consult_id) { err.value = r.error || 'could not open consult'; return; }
    consultId.value = r.consult_id; slice.value = r.slice ?? null; agreed.value = true;
    // seed two independent reads so the result has something to show; the Doctor tab adds more live
    await submitOpinion(consultId.value, 'Cardiologist', 'Early high blood pressure — monitor and adjust lifestyle', 'high');
    await submitOpinion(consultId.value, 'Cardiologist', 'Early high blood pressure — monitor and adjust lifestyle', 'moderate');
    await submitOpinion(consultId.value, 'Internist', 'More tests before calling it hypertension', 'moderate');
    await refresh();
  } catch (e) { err.value = e instanceof Error ? e.message : 'consult unreachable'; }
  finally { busy.value = false; }
}
async function refresh() { if (consultId.value) agg.value = await consultResult(consultId.value); }

// Doctor's independent read
const read = ref('');
const conf = ref<'low' | 'moderate' | 'high'>('moderate');
const submitted = ref(false);
async function submitRead() {
  if (!read.value.trim() || !consultId.value) return;
  busy.value = true;
  try { await submitOpinion(consultId.value, 'Reviewer', read.value.trim(), conf.value); submitted.value = true; read.value = ''; await refresh(); }
  finally { busy.value = false; }
}

const obs = computed(() => slice.value?.systems.flatMap((s) => s.observations) ?? []);
const conds = computed(() => slice.value?.systems.flatMap((s) => s.conditions) ?? []);
const c = computed(() => agg.value?.concordance ?? null);
const top = computed(() => c.value?.groups?.[0] ?? null);
const rest = computed(() => c.value?.groups?.slice(1) ?? []);
const lc = (s: string) => s.replace(/^./, (m) => m.toLowerCase());
// `assessment` is free text a reviewer types into the Doctor tab, and the verdict used to
// be built as an HTML string rendered with v-html — so a read containing markup executed
// in the patient's browser, the one party here who wrote none of it.
//
// Escaping the interpolation would close today's hole and leave the shape that caused it:
// the next value someone interpolates has to remember to escape too. So the verdict is
// structured data now, rendered through ordinary text bindings, and there is no v-html on
// this page to reintroduce the problem.
type Verdict =
  | { kind: 'waiting' }
  | { kind: 'split' }
  | { kind: 'agreed'; headline: string; assessment: string };
const verdict = computed<Verdict>(() => {
  const cc = c.value; const t = top.value;
  if (!cc || cc.n < 2) return { kind: 'waiting' };
  // n >= 2 does not guarantee a group survived grouping; `t!` threw on an empty list.
  if (!t) return { kind: 'waiting' };
  if (cc.verdict === 'split') return { kind: 'split' };
  const headline = cc.verdict === 'unanimous'
    ? `All ${cc.n} doctors agree`
    : `${t.count} of ${cc.n} doctors agree`;
  return { kind: 'agreed', headline, assessment: lc(t.assessment) };
});
const dissentText = computed(() => {
  const cc = c.value; const t = top.value; const r = rest.value;
  if (!cc || cc.n < 2 || cc.verdict === 'unanimous') return '';
  if (!t) return '';   // same empty-groups case as the verdict above
  if (cc.verdict === 'split') return r.concat([t]).map((g) => `${g.count} say ${lc(g.assessment)}`).join('; ') + '.';
  const alt = r[0]; const d = cc.n - t.count;
  return alt ? `${d} ${d > 1 ? 'doctors' : 'doctor'} would instead ${lc(alt.assessment)}.` : '';
});
function spark(t?: number[]): string {
  if (!t || t.length < 2) return '';
  const min = Math.min(...t), max = Math.max(...t), rng = max - min || 1;
  return t.map((v, i) => `${(i / (t.length - 1)) * 60},${18 - ((v - min) / rng) * 16}`).join(' ');
}
const sure: Record<string, string> = { low: 'unsure', moderate: 'fairly sure', high: 'very sure' };

onMounted(() => { /* patient starts at the consent gate */ });
</script>

<template>
  <div class="cv">
    <div class="cv-tabs">
      <button class="cv-tab" :class="{ on: role === 'patient' }" @click="role = 'patient'">Patient</button>
      <button class="cv-tab" :class="{ on: role === 'doctor' }" @click="role = 'doctor'" :disabled="!agreed">Doctor</button>
      <button class="cv-tab" :class="{ on: role === 'coord' }" @click="role = 'coord'" :disabled="!agreed">Coordinator</button>
    </div>
    <p v-if="err" class="cv-err">{{ err }}</p>

    <!-- PATIENT: consent gate → result -->
    <section v-if="role === 'patient'">
      <template v-if="!agreed">
        <div class="cv-eyebrow">Before we ask anyone</div>
        <h2 class="cv-title">Share your record for an independent second opinion?</h2>
        <p class="cv-lede">We'll show verified doctors your <b>medical facts, anonymously</b>. You decide what's shared, and can stop anytime. Nothing goes out until you agree.</p>
        <div class="cv-cols">
          <div><h3 class="cv-h ok">What we'll share</h3><ul class="cv-list"><li><i class="y">✓</i>Medical facts — labs, blood pressure, conditions</li><li><i class="y">✓</i>Your age range and sex <em>doctors need these</em></li><li><i class="y">✓</i>Nothing that identifies you</li></ul></div>
          <div><h3 class="cv-h">What stays hidden</h3><ul class="cv-list"><li><i class="n">·</i>Your name &amp; contacts</li><li><i class="n">·</i>Exact dates &amp; clinics</li><li><i class="n">·</i>Your identity — from every doctor</li></ul></div>
        </div>
        <label class="cv-agree"><input type="checkbox" v-model="accepted" /><span>I agree to share my <b>de-identified</b> record for an independent second opinion, on these terms.</span></label>
        <button class="cv-go" :disabled="busy || !accepted" @click="agree">{{ busy ? 'Asking doctors…' : 'Get my second opinion' }}</button>
        <p class="cv-fine">Opinions to help — not a diagnosis. A doctor makes the call. Your record stays yours.</p>
      </template>
      <template v-else>
        <div class="cv-eyebrow">Your second opinion</div>
        <h2 class="cv-title">What the doctors thought</h2>
        <div v-if="c" class="cv-result">
          <p class="cv-verdict"><template v-if="verdict.kind === 'waiting'">Waiting for at least two reviews to compare.</template><template v-else-if="verdict.kind === 'split'">The doctors are <b>split</b> — no shared view yet.</template><template v-else><span class="agree">{{ verdict.headline }}</span> — {{ verdict.assessment }}.</template></p>
          <p v-if="dissentText" class="cv-dissent">{{ dissentText }}</p>
          <p class="cv-status"><span class="cv-tally"><i v-for="(_, i) in c.n" :key="i" :class="i < (top?.count ?? 0) ? 'a' : 'd'"></i></span><span class="cv-rep">{{ c.n }} reviewed privately</span></p>
        </div>
        <div class="cv-means"><b>What this means.</b> That's agreement among independent doctors — <i>not</i> a diagnosis. The next step is a conversation with your own doctor.</div>
        <div class="cv-priv"><div><span class="yes">Kept private</span> They saw your medical facts — not your name.</div><div><span class="yes">Logged</span> Every look was receipted.</div></div>
      </template>
    </section>

    <!-- DOCTOR: blinded record + one read -->
    <section v-else-if="role === 'doctor'">
      <div class="cv-eyebrow">Independent review · {{ slice?.subject.pseudonym }}</div>
      <h2 class="cv-title">Your independent read</h2>
      <p class="cv-lede">You can't see who the patient is, or what the other doctors think — that keeps each read independent.</p>
      <div class="cv-subj">Adult · {{ slice?.subject.ageBand }} · {{ slice?.subject.sex }} <span>— identity hidden, clinical details kept</span></div>
      <div class="cv-recs">
        <div v-for="o in obs" :key="o.code" class="cv-rr">
          <span class="rn">{{ o.display }}</span>
          <svg v-if="spark(o.trend)" class="cv-spark" viewBox="0 0 60 18" preserveAspectRatio="none"><polyline :points="spark(o.trend)" /></svg><span v-else></span>
          <span class="rv" :class="{ hi: (o.refHigh != null && o.value > o.refHigh) }"><b>{{ o.value }}</b> {{ o.unit }} · ref {{ o.refLow ?? '—' }}–{{ o.refHigh ?? '—' }}</span>
          <span class="src">from lab</span>
        </div>
        <div v-for="cd in conds" :key="cd.display" class="cv-rr"><span class="rn">Problem list</span><span></span><span class="rv">{{ cd.display }}</span><span class="src">clinician-recorded</span></div>
      </div>
      <template v-if="!submitted">
        <label class="cv-lbl">Your assessment</label>
        <textarea v-model="read" rows="2" class="cv-ta" placeholder="What's your independent read of this record?"></textarea>
        <div class="cv-conf"><span>How sure?</span><button v-for="k in (['low','moderate','high'] as const)" :key="k" class="cv-pill" :class="{ on: conf === k }" @click="conf = k">{{ sure[k] }}</button></div>
        <button class="cv-go" :disabled="busy || !read.trim()" @click="submitRead">Submit my independent read</button>
        <p class="cv-blind">🔒 Other reviewers' opinions stay hidden until you submit. Your read is one independent opinion — not the patient's diagnosis.</p>
      </template>
      <p v-else class="cv-ok">✓ Recorded — your read joins the others. See the combined result on the Coordinator tab.</p>
    </section>

    <!-- COORDINATOR: who reviewed + result -->
    <section v-else>
      <div class="cv-eyebrow">Second opinions · double-blind</div>
      <h2 class="cv-title">{{ slice?.subject.pseudonym }} <span class="th">— everyone anonymous</span></h2>
      <div v-if="c" class="cv-result">
        <p class="cv-verdict"><template v-if="verdict.kind === 'waiting'">Waiting for at least two reviews to compare.</template><template v-else-if="verdict.kind === 'split'">The doctors are <b>split</b> — no shared view yet.</template><template v-else><span class="agree">{{ verdict.headline }}</span> — {{ verdict.assessment }}.</template></p>
        <p v-if="dissentText" class="cv-dissent">{{ dissentText }}</p>
        <p class="cv-status"><span class="cv-tally"><i v-for="(_, i) in c.n" :key="i" :class="i < (top?.count ?? 0) ? 'a' : 'd'"></i></span><span class="cv-rep">{{ c.n }} replied · verdict: {{ c.verdict }}</span></p>
      </div>
      <div class="cv-h-row"><h3 class="cv-h">Who reviewed</h3><span class="cv-trust">✓ verified &amp; licensed · anonymous to each other</span></div>
      <div class="cv-roster">
        <div v-for="(o, i) in agg?.opinions ?? []" :key="i" class="cv-row"><span class="doc">{{ o.reviewer }} <span class="dim">#{{ i + 1 }}</span> <span class="vf">✓</span></span><span class="said">{{ o.assessment }}</span><span class="meta">{{ sure[o.confidence] }}</span></div>
      </div>
      <div class="cv-priv"><div><span class="yes">Shared</span> the medical facts.</div><div><span class="no">Hidden</span> the patient's identity, and every doctor's — from each other.</div></div>
    </section>

    <p class="cv-foot">⚕ Opinions gathered to help — not a diagnosis. Consented &amp; receipted. Synthetic sample data.</p>
  </div>
</template>

<style scoped>
.cv { font: 14px/1.55 var(--ui); color: var(--ink); max-width: 640px; }
.cv-tabs { display: inline-flex; gap: 2px; background: var(--sunken); border-radius: var(--pill); padding: 3px; margin-bottom: var(--sp-4); }
.cv-tab { border: 0; background: transparent; color: var(--muted); border-radius: var(--pill); padding: 5px 15px; font: inherit; font-size: 12.5px; cursor: pointer; }
.cv-tab.on { background: var(--accent); color: #04122e; font-weight: 600; } .cv-tab:disabled { opacity: .4; cursor: not-allowed; }
.cv-err { color: var(--fail); font-size: 12.5px; }
.cv-eyebrow { font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--faint); }
.cv-title { font-size: 1.5rem; letter-spacing: -.015em; margin: .1em 0 .25em; font-weight: 600; } .cv-title .th { font-weight: 400; font-size: .9rem; color: var(--muted); }
.cv-lede { color: var(--ink-2); margin: 0 0 var(--sp-4); }
.cv-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--sp-4); padding: var(--sp-3) 0; border-top: 1px solid var(--hairline); border-bottom: 1px solid var(--hairline); margin-bottom: var(--sp-3); }
@media (max-width: 520px) { .cv-cols { grid-template-columns: 1fr; } }
.cv-h { font-size: 11px; text-transform: uppercase; letter-spacing: .07em; color: var(--muted); font-weight: 700; margin: 0 0 .6em; } .cv-h.ok { color: var(--ok); }
.cv-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: .5em; }
.cv-list li { display: grid; grid-template-columns: 1.1em 1fr; gap: .4em; font-size: .95rem; color: var(--ink-2); } .cv-list li em { display: block; font-style: normal; color: var(--faint); font-size: .85em; }
.cv-list i { font-weight: 700; } .cv-list .y { color: var(--ok); } .cv-list .n { color: var(--faint); }
.cv-agree { display: flex; gap: .55em; align-items: flex-start; margin: 0 0 .9em; cursor: pointer; }
.cv-agree input { margin-top: .2em; accent-color: var(--accent); }
.cv-go { width: 100%; background: var(--accent); color: #04122e; border: 0; border-radius: var(--r-2); padding: 10px; font: inherit; font-weight: 600; cursor: pointer; } .cv-go:disabled { opacity: .5; cursor: not-allowed; }
.cv-fine { font-size: 11px; color: var(--faint); text-align: center; margin: .6em 0 0; }
.cv-result { border-top: 1px solid var(--hairline); border-bottom: 1px solid var(--hairline); padding: var(--sp-3) 0; margin-bottom: var(--sp-3); }
.cv-verdict { font-size: 1.3rem; line-height: 1.4; margin: 0; } .cv-verdict :deep(.agree) { color: var(--ok); }
.cv-dissent { color: var(--warn); margin: .35em 0 0; font-size: 1rem; }
.cv-status { display: flex; align-items: center; gap: .6em; margin: .85em 0 0; }
.cv-tally { display: inline-flex; gap: 5px; } .cv-tally i { width: 10px; height: 10px; border-radius: 50%; } .cv-tally i.a { background: var(--ok); } .cv-tally i.d { background: var(--warn); }
.cv-rep { font-size: 11.5px; color: var(--muted); }
.cv-means { background: var(--accent-wash); border: 1px solid var(--accent); border-radius: var(--r-3); padding: .9em 1.1em; font-size: .96rem; color: var(--ink-2); margin-bottom: var(--sp-3); } .cv-means b { color: var(--ink); } .cv-means i { font-style: italic; }
.cv-priv { display: flex; flex-direction: column; gap: .35em; font-size: .93rem; color: var(--ink-2); } .cv-priv .yes { color: var(--ok); font-weight: 600; margin-right: .3em; } .cv-priv .no { color: var(--muted); font-weight: 600; margin-right: .3em; }
.cv-subj { font-size: .95rem; background: var(--sunken); border: 1px dashed var(--hairline-strong); border-radius: var(--r-2); padding: .5em .8em; margin-bottom: .7em; } .cv-subj span { color: var(--muted); font-size: .88em; }
.cv-recs { display: flex; flex-direction: column; margin-bottom: var(--sp-3); }
.cv-rr { display: grid; grid-template-columns: 9em 60px 1fr auto; align-items: center; gap: 1em; padding: .5em 0; border-top: 1px solid var(--hairline); font-size: .92rem; } .cv-rr:first-child { border-top: 0; }
.cv-rr .rn { color: var(--ink); } .cv-rr .rv { font-variant-numeric: tabular-nums; color: var(--ink-2); font-size: .9rem; } .cv-rr .rv b { color: var(--ink); } .cv-rr .rv.hi b { color: var(--fail); } .cv-rr .src { font-size: 10.5px; color: var(--faint); text-align: right; }
.cv-spark { width: 60px; height: 18px; } .cv-spark polyline { fill: none; stroke: var(--fail); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.cv-lbl { display: block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; color: var(--muted); margin-bottom: 5px; }
.cv-ta { width: 100%; box-sizing: border-box; background: var(--surface); border: 1px solid var(--hairline-strong); border-radius: var(--r-2); color: var(--ink); padding: .6em .7em; font: inherit; resize: vertical; }
.cv-conf { display: flex; align-items: center; gap: 6px; margin: .7em 0; font-size: 11.5px; color: var(--muted); }
.cv-pill { border: 1px solid var(--hairline-strong); background: var(--surface); color: var(--ink-2); border-radius: var(--pill); padding: 3px 12px; font: inherit; font-size: 11.5px; cursor: pointer; } .cv-pill.on { background: var(--accent-wash); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.cv-blind { font-size: 11.5px; color: var(--muted); margin: .7em 0 0; } .cv-ok { color: var(--ok); font-size: .95rem; }
.cv-h-row { display: flex; align-items: baseline; justify-content: space-between; gap: 1em; margin: 0 0 .5em; } .cv-trust { font-size: 11px; color: var(--ok); }
.cv-roster { display: flex; flex-direction: column; margin-bottom: var(--sp-3); }
.cv-row { display: grid; grid-template-columns: 11em 1fr auto; align-items: baseline; gap: 1em; padding: .55em 0; border-top: 1px solid var(--hairline); } .cv-row:first-child { border-top: 0; }
.cv-row .doc { font-weight: 600; } .cv-row .dim { color: var(--muted); font-weight: 400; } .cv-row .vf { color: var(--ok); } .cv-row .said { color: var(--ink-2); } .cv-row .meta { font-size: 11px; color: var(--muted); text-align: right; }
.cv-foot { font-size: 11px; color: var(--faint); border-top: 1px solid var(--hairline); padding-top: .8em; margin-top: var(--sp-3); }
</style>
