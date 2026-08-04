// vision.ts — multimodal image intake (verb 1 Observe; use cases #1 wound + #2 skin). Routes an image
// to a vision-language model (Ollama LLaVA by default) with a strictly NON-DIAGNOSTIC clinical-
// observation prompt: describe what is VISIBLE (a wound, rash, swelling, redness, bleeding) and surface
// visual DANGER SIGNS — never a diagnosis. Detected visual red flags raise an escalate signal that
// feeds the triage/imaging core. GRACEFUL DEGRADATION: if no vision model is reachable it returns
// degraded:true and fabricates NOTHING (the anti-Watson floor for images — silence over a made-up
// finding). Only the model's own words are surfaced; the twin never invents what it cannot see.
import { mintId } from './ids.js';

const OLLAMA = (process.env.NOETICA_OLLAMA_URL ?? process.env.OLLAMA_HOST ?? 'http://127.0.0.1:11434').replace(/\/$/, '');
const VISION_MODEL = process.env.HEALTH_TWIN_VISION_MODEL ?? 'llava';

// Visual danger signs (matched against the model's OWN description, negation-aware). Safety-first.
const VISUAL_RED_FLAGS: { any: string[]; reason: string }[] = [
  { any: ['spreading redness', 'red streak', 'red streaks', 'streaking'], reason: 'possible spreading infection / lymphangitis' },
  { any: ['pus', 'purulent', 'abscess', 'discharge'], reason: 'possible infected wound' },
  { any: ['necrosis', 'necrotic', 'black tissue', 'dead tissue', 'gangren'], reason: 'possible tissue death' },
  { any: ['deep wound', 'exposed', 'bone visible', 'tendon visible', 'gaping'], reason: 'deep/complex wound' },
  { any: ['heavy bleeding', 'profuse', 'soaked', 'active bleeding'], reason: 'possible significant bleeding' },
  { any: ['blue', 'cyanotic', 'dusky', 'pale and cold'], reason: 'possible circulation compromise' },
  { any: ['blistering', 'charred', 'full thickness', 'third degree'], reason: 'possible severe burn' },
];
const NEG = /\b(no|not|without|absent|no signs? of|no evidence of)\b/;
function present(lower: string, phrase: string): boolean {
  let idx = lower.indexOf(phrase);
  while (idx !== -1) {
    const start = Math.max(lower.lastIndexOf('.', idx), lower.lastIndexOf(',', idx), lower.lastIndexOf(';', idx)) + 1;
    if (!NEG.test(lower.slice(start, idx))) return true;
    idx = lower.indexOf(phrase, idx + phrase.length);
  }
  return false;
}

const PROMPT =
  'You are a careful clinical OBSERVATION assistant, not a diagnostician. Describe ONLY what is ' +
  'visibly present in this image of a body area or wound: location, size impression, color, swelling, ' +
  'bleeding, discharge, and skin changes. Explicitly note any visible danger signs (spreading redness, ' +
  'red streaks, pus, necrosis/black tissue, deep or gaping wound, heavy bleeding, blue/dusky skin, ' +
  'severe blistering). Do NOT state a diagnosis or name a disease. Be concise and factual. If the image ' +
  'is not a medical image, say so.';

export interface VisionReading {
  ok: boolean;
  degraded: boolean;                 // true = no vision model; NOTHING fabricated
  modelUsed?: string;
  visibleFindings: string;           // the model's own description (empty when degraded)
  visualRedFlags: { term: string; reason: string }[];
  escalate: boolean;
  followUpQuestions: string[];
  receipt: string;
  disclaimer: string;
}

// Base64 image → non-diagnostic visual observation. Strips a data: URI prefix if present.
export async function assessImage(imageBase64: string): Promise<VisionReading> {
  const receipt = mintId('receipt');
  const disclaimer = 'Non-diagnostic visual observation of an image — describes what is visible and flags danger signs; it does not diagnose. A clinician (and often an in-person exam) decides.';
  const b64 = (imageBase64 ?? '').replace(/^data:image\/[a-zA-Z0-9.+-]+;base64,/, '').trim();
  const degraded = (msg: string): VisionReading => ({ ok: false, degraded: true, visibleFindings: '', visualRedFlags: [], escalate: false, followUpQuestions: ['Can you describe what you see in plain words (location, size, color, bleeding, pain)?'], receipt, disclaimer: `${disclaimer} (${msg})` });

  if (!b64) return degraded('no image provided');
  try {
    const ac = new AbortController(); const t = setTimeout(() => ac.abort(), 120_000); // vision on CPU is slow
    const r = await fetch(`${OLLAMA}/api/generate`, {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ model: VISION_MODEL, prompt: PROMPT, images: [b64], stream: false, options: { temperature: 0.2 } }),
      signal: ac.signal,
    });
    clearTimeout(t);
    if (!r.ok) return degraded(`vision model unreachable (HTTP ${r.status})`);
    const d = await r.json() as { response?: string };
    const findings = (d.response ?? '').trim();
    if (!findings) return degraded('vision model returned nothing');

    const lower = findings.toLowerCase();
    const visualRedFlags: { term: string; reason: string }[] = [];
    for (const rf of VISUAL_RED_FLAGS) for (const p of rf.any) if (present(lower, p)) { visualRedFlags.push({ term: p, reason: rf.reason }); break; }

    return {
      ok: true, degraded: false, modelUsed: VISION_MODEL,
      visibleFindings: findings, visualRedFlags, escalate: visualRedFlags.length > 0,
      followUpQuestions: [
        'How long has it looked like this, and is it changing?',
        'Any fever, spreading redness, numbness, or worsening pain?',
        'Is this over a joint, the face, or a large area?',
      ],
      receipt, disclaimer,
    };
  } catch (e) {
    return degraded((e as Error).name === 'AbortError' ? 'vision model timeout' : 'vision model error');
  }
}
