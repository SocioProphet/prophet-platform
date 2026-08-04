<script setup lang="ts">
// Mail — ported from app-vue into the cockpit. A Hey-style split inbox (Imbox / Feed /
// Paper Trail) with a Screener, ⌘K palette, keyboard model, and AI draft/summary over the
// sovereign choir. Reuses the ported useMail store + shared mailApi. Restyled to dark tokens.
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useMail } from '../stores/mail';
import type { MailView } from '../services/mailApi';

const mail = useMail();
const reply = ref('');
const replySending = ref(false);
const paletteQuery = ref('');
const composeTo = ref('');
const composeSubject = ref('');
const composeBody = ref('');
const composeSending = ref(false);

async function submitReply() {
  if (!reply.value.trim() || replySending.value) return;
  replySending.value = true;
  try { await mail.replyToCurrent(reply.value); reply.value = ''; }
  catch { /* mail.error already set */ }
  finally { replySending.value = false; }
}
async function loadDraft() { const draft = await mail.draftReply('reply'); if (draft) reply.value = draft; }
function openCompose() { composeTo.value = ''; composeSubject.value = ''; composeBody.value = ''; mail.composeOpen = true; }
async function submitCompose() {
  if (composeSending.value) return;
  composeSending.value = true;
  try { if (await mail.sendNew({ to: composeTo.value, subject: composeSubject.value, body: composeBody.value })) mail.composeOpen = false; }
  finally { composeSending.value = false; }
}

const views: { key: MailView; label: string; glyph: string }[] = [
  { key: 'imbox', label: 'Imbox', glyph: '▤' },
  { key: 'feed', label: 'The Feed', glyph: '≋' },
  { key: 'papertrail', label: 'Paper Trail', glyph: '▦' },
];
const actions = [
  { id: 'done', label: 'Mark done', key: 'E', run: () => mail.act('done') },
  { id: 'replyLater', label: 'Reply later', key: 'R', run: () => mail.act('replyLater', { until: 'later' }) },
  { id: 'setAside', label: 'Set aside', key: 'S', run: () => mail.act('setAside') },
  { id: 'snooze', label: 'Snooze 3 days', key: 'H', run: () => mail.act('snooze', { until: '+3d' }) },
  { id: 'imbox', label: 'Go to Imbox', key: 'G I', run: () => mail.load('imbox') },
  { id: 'feed', label: 'Go to The Feed', key: 'G F', run: () => mail.load('feed') },
  { id: 'screener', label: 'Open Screener', key: 'G S', run: () => (mail.screenerOpen = true) },
];
const filteredActions = computed(() => actions.filter((a) => a.label.toLowerCase().includes(paletteQuery.value.toLowerCase())));
function runAction(a: { run: () => void }) { a.run(); mail.paletteOpen = false; paletteQuery.value = ''; }

function onKey(e: KeyboardEvent) {
  const typing = (e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA/);
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); mail.paletteOpen = !mail.paletteOpen; return; }
  if (e.key === 'Escape') { mail.paletteOpen = false; mail.screenerOpen = false; mail.composeOpen = false; return; }
  if (mail.paletteOpen || mail.composeOpen || typing) return;
  if (e.key === 'j') mail.selectRelative(1);
  else if (e.key === 'k') mail.selectRelative(-1);
  else if (e.key === 'e') mail.act('done');
  else if (e.key === 'r') mail.act('replyLater', { until: 'later' });
  else if (e.key === 's') mail.act('setAside');
  else if (e.key === 'c') openCompose();
}
onMounted(() => { mail.load('imbox'); mail.loadScreener(); window.addEventListener('keydown', onKey); });
onUnmounted(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <div class="mx">
    <aside class="mx-rail">
      <button class="mx-compose" @click="openCompose">✎ Compose <span class="mx-kbd">C</span></button>
      <button v-for="v in views" :key="v.key" class="mx-nav" :class="{ on: mail.view === v.key }" @click="mail.load(v.key)">
        <span class="mx-glyph">{{ v.glyph }}</span> {{ v.label }}
        <span v-if="v.key === 'imbox' && mail.unreadCount" class="mx-count">{{ mail.unreadCount }}</span>
      </button>
      <button class="mx-nav" @click="mail.screenerOpen = true">
        <span class="mx-glyph">◫</span> Screener
        <span v-if="mail.screener.length" class="mx-badge">{{ mail.screener.length }}</span>
      </button>
      <div class="mx-foot">⚿ on-device · no tracking</div>
    </aside>

    <section class="mx-list">
      <header class="mx-listhead">
        <span>{{ views.find((v) => v.key === mail.view)?.label }}</span>
        <span v-if="mail.replyLaterCount" class="mx-muted">reply-later · {{ mail.replyLaterCount }}</span>
      </header>
      <p v-if="mail.error" class="mx-err">{{ mail.error }}</p>
      <p v-else-if="mail.loading" class="mx-muted mx-pad">Loading…</p>
      <p v-else-if="!mail.threads.length" class="mx-muted mx-pad">Nothing here. Inbox zero.</p>
      <button v-for="t in mail.threads" :key="t.id" class="mx-row" :class="{ on: mail.current?.id === t.id, unread: t.unread }" @click="mail.select(t.id)">
        <div class="mx-rowtop"><span class="mx-from">{{ t.from }}</span><span class="mx-ts">{{ t.ts }}</span></div>
        <div class="mx-subj">{{ t.subject }} <span v-if="t.replyLaterAt" class="mx-later" :title="'reply later · ' + t.replyLaterAt">◷</span></div>
        <div class="mx-snip">{{ t.snippet }}</div>
      </button>
    </section>

    <section class="mx-read" v-if="mail.current">
      <header class="mx-readhead">
        <div class="mx-who"><div class="mx-bigsubj">{{ mail.current.subject }}</div>
          <div class="mx-muted">{{ mail.current.from }} · {{ mail.current.fromEmail }} · {{ mail.current.ts }}</div></div>
        <button class="mx-act" title="reply later (R)" @click="mail.act('replyLater', { until: 'later' })">◷</button>
        <button class="mx-act" title="set aside (S)" @click="mail.act('setAside')">▢</button>
        <button class="mx-act ok" title="done (E)" @click="mail.act('done')">✓</button>
      </header>
      <div v-if="mail.aiSummary" class="mx-ai">✦ {{ mail.aiSummary }}</div>
      <div class="mx-body"><p v-for="m in mail.current.messages" :key="m.id">{{ m.bodyText }}</p></div>
      <footer class="mx-replybar">
        <input v-model="reply" placeholder="Reply…" :disabled="replySending" @keyup.enter="submitReply" />
        <button class="mx-draft" title="AI draft" @click="loadDraft">⚡ AI draft</button>
        <button class="mx-send" :disabled="!reply.trim() || replySending" @click="submitReply">{{ replySending ? 'Sending…' : 'Send' }}</button>
      </footer>
    </section>
    <section class="mx-read mx-empty" v-else>Select a conversation</section>

    <div v-if="mail.paletteOpen" class="mx-overlay" @click.self="mail.paletteOpen = false">
      <div class="mx-palette">
        <input v-model="paletteQuery" placeholder="Type a command…" autofocus />
        <button v-for="a in filteredActions" :key="a.id" class="mx-palrow" @click="runAction(a)">
          <span>{{ a.label }}</span><span class="mx-kbd">{{ a.key }}</span>
        </button>
      </div>
    </div>

    <div v-if="mail.screenerOpen" class="mx-overlay" @click.self="mail.screenerOpen = false">
      <div class="mx-modal">
        <h3>The Screener — {{ mail.screener.length }} first-time senders</h3>
        <p class="mx-muted mx-small">Approve once and they reach your Imbox forever. Deny and you never see them again.</p>
        <div v-for="s in mail.screener" :key="s.id" class="mx-scrow">
          <div><div class="mx-from">{{ s.from }}</div><div class="mx-muted mx-small">{{ s.fromEmail }} — {{ s.subjectPreview }}</div></div>
          <div class="mx-scbtns"><button class="yes" @click="mail.screen(s.id, 'approve')">Yes</button><button class="no" @click="mail.screen(s.id, 'deny')">No</button></div>
        </div>
        <p v-if="!mail.screener.length" class="mx-muted mx-pad">Screener clear.</p>
      </div>
    </div>

    <div v-if="mail.composeOpen" class="mx-overlay" @click.self="mail.composeOpen = false">
      <div class="mx-modal">
        <h3>New message</h3>
        <p v-if="mail.error" class="mx-err">{{ mail.error }}</p>
        <input v-model="composeTo" placeholder="To" autofocus />
        <input v-model="composeSubject" placeholder="Subject" />
        <textarea v-model="composeBody" placeholder="Write something…" rows="8" />
        <div class="mx-composebtns">
          <button class="cancel" @click="mail.composeOpen = false">Cancel</button>
          <button class="mx-send" :disabled="!composeTo.trim() || !composeSubject.trim() || composeSending" @click="submitCompose">{{ composeSending ? 'Sending…' : 'Send' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mx { display: grid; grid-template-columns: 190px 300px 1fr; height: 100%; min-height: 0; font-size: 0.85rem; background: var(--bg); color: var(--text); }
.mx-rail { border-right: 1px solid var(--line); padding: 0.75rem; display: flex; flex-direction: column; gap: 0.15rem; }
.mx-compose { display: flex; align-items: center; gap: 0.5rem; background: var(--accent); color: #17130a; border: 0; border-radius: 8px; padding: 0.5rem 0.65rem; margin-bottom: 0.5rem; cursor: pointer; font-weight: 700; font-size: 0.82rem; } .mx-compose:hover { filter: brightness(1.06); }
.mx-nav { display: flex; align-items: center; gap: 0.55rem; padding: 0.45rem 0.6rem; border: 0; background: none; border-radius: 8px; cursor: pointer; text-align: left; color: var(--text-2); font-size: 0.84rem; }
.mx-nav:hover { background: rgba(255,255,255,0.03); } .mx-nav.on { background: var(--accent-soft); color: var(--accent); font-weight: 550; }
.mx-glyph { width: 1rem; text-align: center; opacity: 0.8; }
.mx-count, .mx-badge { margin-left: auto; font-size: 0.7rem; } .mx-badge { background: rgba(227,179,65,0.18); color: var(--amber); border-radius: 999px; padding: 0 0.45rem; }
.mx-foot { margin-top: auto; font-size: 0.68rem; color: var(--text-3); display: flex; gap: 0.35rem; align-items: center; }
.mx-list { border-right: 1px solid var(--line); overflow-y: auto; display: flex; flex-direction: column; }
.mx-listhead { display: flex; justify-content: space-between; align-items: baseline; padding: 0.6rem 0.85rem; border-bottom: 1px solid var(--line); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; color: var(--text-2); position: sticky; top: 0; background: var(--bg); z-index: 1; }
.mx-row { display: block; width: 100%; text-align: left; padding: 0.55rem 0.75rem; border: 0; border-bottom: 1px solid var(--line); background: none; color: inherit; cursor: pointer; }
.mx-row:hover { background: rgba(255,255,255,0.02); } .mx-row.on { background: var(--accent-soft); border-left: 2px solid var(--accent); }
.mx-row.unread .mx-from, .mx-row.unread .mx-subj { font-weight: 640; color: var(--text); }
.mx-rowtop { display: flex; justify-content: space-between; } .mx-from { color: var(--text); } .mx-ts { font-size: 0.7rem; color: var(--text-3); }
.mx-subj { color: var(--text-2); margin: 0.1rem 0; } .mx-snip { color: var(--text-3); font-size: 0.78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mx-later { color: var(--amber); }
.mx-read { display: flex; flex-direction: column; overflow: hidden; } .mx-read.mx-empty { align-items: center; justify-content: center; color: var(--text-3); }
.mx-readhead { display: flex; align-items: center; gap: 0.6rem; padding: 0.75rem 1rem; border-bottom: 1px solid var(--line); }
.mx-who { flex: 1; } .mx-bigsubj { font-size: 1rem; font-weight: 560; }
.mx-act { width: 2rem; height: 2rem; border: 1px solid var(--line-2); background: var(--surface); border-radius: 8px; cursor: pointer; color: var(--text-2); } .mx-act.ok { color: var(--live); }
.mx-ai { margin: 0.75rem 1rem; padding: 0.5rem 0.75rem; background: var(--accent-soft); color: var(--accent); border-radius: 8px; font-size: 0.8rem; }
.mx-body { padding: 0.5rem 1rem; line-height: 1.7; overflow-y: auto; flex: 1; color: var(--text-2); }
.mx-replybar { display: flex; gap: 0.6rem; align-items: center; padding: 0.75rem 1rem; border-top: 1px solid var(--line); }
.mx-replybar input { flex: 1; padding: 0.55rem 0.75rem; border: 1px solid var(--line-2); border-radius: 8px; background: var(--bg); color: var(--text); }
.mx-draft, .mx-send, .mx-composebtns button, .mx-scbtns button { padding: 0.5rem 0.85rem; border-radius: 8px; border: 1px solid var(--line-2); background: var(--surface); cursor: pointer; color: var(--text-2); }
.mx-send { background: var(--accent); color: #17130a; border: 0; font-weight: 700; } .mx-send:hover:not(:disabled) { filter: brightness(1.06); } .mx-send:disabled, .mx-draft:disabled { opacity: 0.5; cursor: default; }
.mx-badge { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 700; }
.mx-muted { color: var(--text-3); } .mx-small { font-size: 0.74rem; } .mx-pad { padding: 1rem; } .mx-err { color: var(--down); padding: 0.75rem; }
.mx-overlay { position: absolute; inset: 0; background: rgba(0,0,0,0.5); display: flex; align-items: flex-start; justify-content: center; padding-top: 12vh; z-index: 40; }
.mx-palette, .mx-modal { background: var(--surface); width: 520px; max-width: 92vw; border-radius: 12px; box-shadow: 0 20px 60px -20px rgba(0,0,0,0.7); border: 1px solid var(--line-2); padding: 0.85rem; display: flex; flex-direction: column; gap: 0.6rem; }
.mx-palette input, .mx-modal input, .mx-modal textarea { width: 100%; padding: 0.6rem 0.75rem; border: 1px solid var(--line-2); border-radius: 8px; background: var(--bg); color: var(--text); font: inherit; box-sizing: border-box; }
.mx-palrow { display: flex; justify-content: space-between; width: 100%; padding: 0.5rem 0.65rem; border: 0; background: none; cursor: pointer; border-radius: 8px; color: var(--text-2); } .mx-palrow:hover { background: rgba(255,255,255,0.04); }
.mx-kbd { font-family: var(--mono, ui-monospace), monospace; font-size: 0.72rem; color: var(--text-3); }
.mx-scrow { display: flex; justify-content: space-between; align-items: center; padding: 0.55rem 0.35rem; border-bottom: 1px solid var(--line); }
.mx-scbtns button { margin-left: 0.4rem; } .mx-scbtns .yes { color: var(--live); border-color: rgba(63,185,80,0.4); } .mx-scbtns .no { color: var(--down); border-color: rgba(240,101,106,0.4); }
.mx-composebtns { display: flex; justify-content: flex-end; gap: 0.5rem; }
</style>
