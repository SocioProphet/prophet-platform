<script setup lang="ts">
// SourceOS Image Builder — ported from app-vue (the standalone builder) into the unified
// cockpit. Compose a SourceOS image from a flavor and the platform builds it. Reuses the
// cockpit's own buildsApi + Firebase auth store (tier/policy gates; the server still enforces).
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import SurfaceHeader from '../components/SurfaceHeader.vue';
import { useAuth } from '../stores/auth';
import { createBuild, type BuildSpec } from '../services/buildsApi';

const auth = useAuth();
const router = useRouter();

const edition = ref<BuildSpec['edition']>('desktop');
const arch = ref<BuildSpec['arch']>('x86_64');
const hostname = ref('sourceos');
const packagesText = ref('');
const enableSsh = ref(false);
const enableDocker = ref(false);
const usersText = ref('');
const moduleSnippet = ref('');
const err = ref(''); const busy = ref(false);

// Gates from the server-provided policy (server still enforces; UI just reflects).
const advanced = computed(() => !!auth.policy?.services);      // services/users → paid+
const premium = computed(() => !!auth.policy?.moduleEditor);   // raw module → premium
const maxPackages = computed(() => auth.policy?.maxPackages ?? 10);
const lane = computed(() => (auth.tier === 'free'
  ? 'Built on shared CI runners (free tier).'
  : 'Built on a private on-demand VM (paid tier).'));

async function submit() {
  err.value = ''; busy.value = true;
  const packages = packagesText.value.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
  const spec: BuildSpec = { edition: edition.value, arch: arch.value, hostname: hostname.value, packages };
  if (advanced.value) {
    spec.services = { openssh: enableSsh.value, docker: enableDocker.value };
    const users = usersText.value.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean).map((name) => ({ name, groups: ['wheel'] }));
    if (users.length) spec.users = users;
  }
  if (premium.value && moduleSnippet.value.trim()) spec.moduleSnippet = moduleSnippet.value;
  try { await createBuild(spec); router.push('/sourceos/builds'); }
  catch (e: any) { err.value = e?.message ? String(e.message).replace(/^Firebase:\s*/, '') : 'Build request failed.'; }
  finally { busy.value = false; }
}
</script>

<template>
  <section class="ib" aria-label="SourceOS Image Builder">
    <SurfaceHeader title="SourceOS Image Builder" eyebrow="SourceOS · Builder">
      <template #badge><span class="ib-tier">{{ auth.tier }} tier</span></template>
    </SurfaceHeader>
    <p class="ib-lede">Start from a flavor, customize it, and the platform builds a bootable SourceOS image for you.</p>

    <form class="ib-card" @submit.prevent="submit">
      <div class="ib-row">
        <label class="ib-field"><span>Edition</span>
          <select v-model="edition">
            <option value="desktop">Desktop (GNOME)</option>
            <option value="server">Server (headless)</option>
            <option value="edge">Edge (appliance)</option>
          </select>
        </label>
        <label class="ib-field"><span>Architecture</span>
          <select v-model="arch">
            <option value="x86_64">x86_64 (PC)</option>
            <option value="aarch64">ARM64</option>
          </select>
        </label>
      </div>

      <label class="ib-field"><span>Hostname</span>
        <input v-model="hostname" placeholder="sourceos" />
      </label>

      <label class="ib-field"><span>Extra packages <em>space/comma separated nixpkgs names · up to {{ maxPackages }}</em></span>
        <textarea v-model="packagesText" rows="3" placeholder="htop tmux ripgrep" />
      </label>

      <fieldset class="ib-gate" :class="{ locked: !advanced }">
        <legend>Services &amp; users <span v-if="!advanced" class="ib-lock">paid tier</span></legend>
        <div class="ib-checks">
          <label class="ib-check"><input type="checkbox" v-model="enableSsh" :disabled="!advanced" /> OpenSSH</label>
          <label class="ib-check"><input type="checkbox" v-model="enableDocker" :disabled="!advanced" /> Docker</label>
        </div>
        <label class="ib-field"><span>Users <em>space/comma separated; each added to wheel</em></span>
          <input v-model="usersText" :disabled="!advanced" placeholder="alice bob" />
        </label>
      </fieldset>

      <fieldset class="ib-gate" :class="{ locked: !premium }">
        <legend>Custom NixOS module <span v-if="!premium" class="ib-lock">premium</span></legend>
        <label class="ib-field"><span><em>raw module config; sandboxed, validated server-side</em></span>
          <textarea v-model="moduleSnippet" :disabled="!premium" rows="4" placeholder="services.tailscale.enable = true;" />
        </label>
      </fieldset>

      <div class="ib-actions">
        <button class="ib-build" type="submit" :disabled="busy">{{ busy ? 'Submitting…' : 'Build image' }}</button>
        <span class="ib-lane">{{ lane }}</span>
      </div>
      <p v-if="err" class="ib-err" role="alert">{{ err }}</p>
    </form>
  </section>
</template>

<style scoped>
/* Conforms to the annealed epistemic-Carbon language (OperatorDashboard db-* vocabulary):
   hairline var(--line) panels at var(--radius), 0.7rem uppercase bold section heads,
   0.62rem uppercase field labels, 0.56rem badges, accent buttons w/ #17130a ink. */
.ib { height: 100%; min-height: 0; overflow-y: auto; padding: 1rem 1.25rem 2rem; background: var(--bg); color: var(--text); }
.ib-tier { font-size: 0.56rem; text-transform: uppercase; letter-spacing: 0.03em; font-weight: 700; color: var(--accent); background: var(--accent-soft); border-radius: 4px; padding: 0.03rem 0.3rem; }
.ib-lede { margin: 0.3rem 0 0.9rem; max-width: 70ch; font-size: 0.85rem; color: var(--text-3); }
.ib-card { max-width: 640px; display: flex; flex-direction: column; gap: 0.8rem; border: 1px solid var(--line); border-radius: var(--radius, 12px); background: var(--surface); padding: 0.85rem 1rem 1rem; }
.ib-row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; }
.ib-field { display: flex; flex-direction: column; gap: 0.28rem; }
.ib-field > span { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; color: var(--text-3); }
.ib-field em { color: var(--text-3); font-style: normal; font-size: 0.62rem; text-transform: none; letter-spacing: 0; font-weight: 400; }
.ib-field input, .ib-field select, .ib-field textarea { width: 100%; padding: 0.5rem 0.6rem; border: 1px solid var(--line-2); border-radius: 8px; background: var(--bg); color: var(--text); font-size: 0.85rem; font-family: inherit; }
.ib-field textarea { resize: vertical; font-family: var(--mono, ui-monospace), monospace; }
.ib-field input:focus, .ib-field select:focus, .ib-field textarea:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
/* De-boxed gates: hairline separator + uppercase mini-head, not a nested card. */
.ib-gate { border: none; border-top: 1px solid var(--line); border-radius: 0; padding: 0.75rem 0 0; margin: 0.2rem 0 0; display: flex; flex-direction: column; gap: 0.55rem; } .ib-gate.locked { opacity: 0.55; }
.ib-gate legend { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; color: var(--text-2); padding: 0 0 0.45rem; }
.ib-lock { margin-left: 0.45rem; font-size: 0.56rem; letter-spacing: 0.03em; font-weight: 700; color: var(--amber); background: rgba(227,179,65,0.14); border-radius: 4px; padding: 0.03rem 0.3rem; }
.ib-checks { display: flex; gap: 1.2rem; } .ib-check { display: inline-flex; align-items: center; gap: 0.4rem; font-size: 0.82rem; color: var(--text-2); } .ib-check input { accent-color: var(--accent); }
.ib-actions { display: flex; align-items: center; gap: 0.9rem; border-top: 1px solid var(--line); padding-top: 0.8rem; margin-top: 0.2rem; }
.ib-build { padding: 0.45rem 0.95rem; border-radius: 8px; border: none; background: var(--accent); color: #17130a; font-weight: 700; font-size: 0.82rem; cursor: pointer; } .ib-build:hover:not(:disabled) { filter: brightness(1.06); } .ib-build:disabled { opacity: 0.5; cursor: default; }
.ib-lane { font-size: 0.72rem; color: var(--text-3); }
.ib-err { margin: 0.2rem 0 0; font-size: 0.78rem; color: var(--down); background: rgba(240,101,106,0.1); border: 1px solid rgba(240,101,106,0.3); border-radius: 8px; padding: 0.5rem 0.65rem; }
</style>
