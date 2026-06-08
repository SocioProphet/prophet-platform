<script setup lang="ts">
import readiness from '../../../../contracts/health-ai/demo/health-ai-demo-readiness.v0.json'

type UpstreamArtifact = {
  repo: string
  ref: string
  artifacts: string[]
  validation: string
}

type EvalCriterion = {
  criterion_id: string
  status: string
  evidence_ref: string
}

const upstreamArtifacts = readiness.upstream_artifacts as UpstreamArtifact[]
const evalCriteria = readiness.eval_readiness_criteria as EvalCriterion[]
const sourceBasis = readiness.source_basis
const demoSurface = readiness.demo_surface
const blockedActions = readiness.blocked_actions

const safetyFlags = [
  ['Production ready', readiness.production_ready],
  ['Patient-care action', readiness.patient_care_action],
  ['Autonomous clinical action', readiness.autonomous_clinical_action],
  ['Real clinical data processing', readiness.real_clinical_data_processing],
  ['Customer-facing healthcare claim', readiness.customer_facing_healthcare_claim],
  ['Protected benchmark reproduction', readiness.protected_benchmark_reproduction]
]
</script>

<template>
  <section style="border:1px solid #bfdbfe;border-radius:16px;padding:1rem;margin-top:1.5rem;background:#eff6ff;">
    <div style="display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:800;">
          Health-AI demo readiness
        </div>
        <h2 style="margin:.4rem 0 .35rem 0;font-size:1.35rem;font-weight:800;">
          Non-production evaluation surface
        </h2>
        <p style="margin:0;opacity:.78;max-width:820px;">
          Fixture-backed readout for healthcare-AI evaluation and clinical-value planning. This surface distinguishes external source claims, benchmark-design concepts, readiness evidence, and blocked clinical actions.
        </p>
      </div>
      <div style="border:1px solid #93c5fd;border-radius:999px;background:white;padding:.35rem .65rem;font-size:.85rem;font-weight:800;white-space:nowrap;">
        {{ readiness.readiness_state }}
      </div>
    </div>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.75rem;margin-top:1rem;">
      <article
        v-for="([label, value]) in safetyFlags"
        :key="label"
        style="border:1px solid #dbeafe;border-radius:12px;background:white;padding:.75rem;"
      >
        <div style="font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;opacity:.62;font-weight:800;">
          {{ label }}
        </div>
        <div :style="{ marginTop: '.35rem', fontWeight: '850', color: value ? '#991b1b' : '#166534' }">
          {{ value ? 'Enabled' : 'Blocked' }}
        </div>
      </article>
    </section>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:1rem;">
      <article style="border:1px solid #dbeafe;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Source basis</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="source in sourceBasis" :key="source.source_id" style="margin:.45rem 0;">
            <strong>{{ source.source_class }}</strong>
            <div style="font-size:.88rem;opacity:.8;">{{ source.classification }}</div>
            <div style="font-size:.8rem;opacity:.62;"><code>{{ source.source_id }}</code></div>
            <p style="margin:.35rem 0 0 0;font-size:.9rem;">{{ source.notes }}</p>
          </li>
        </ul>
      </article>

      <article style="border:1px solid #dbeafe;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Allowed demo views</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="view in demoSurface.allowed_views" :key="view" style="margin:.3rem 0;">{{ view }}</li>
        </ul>
        <h4 style="margin:.8rem 0 .35rem 0;font-size:.92rem;">Blocked views</h4>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="view in demoSurface.blocked_views" :key="view" style="margin:.3rem 0;">{{ view }}</li>
        </ul>
      </article>
    </section>

    <section style="border:1px solid #dbeafe;border-radius:12px;background:white;padding:.85rem;margin-top:1rem;">
      <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Cross-repo evidence chain</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:.75rem;">
        <article
          v-for="artifact in upstreamArtifacts"
          :key="artifact.repo"
          style="border:1px solid #e2e8f0;border-radius:10px;padding:.7rem;"
        >
          <div style="font-weight:850;">{{ artifact.repo }}</div>
          <div style="font-size:.82rem;opacity:.68;margin-top:.2rem;">{{ artifact.ref }}</div>
          <div style="font-size:.85rem;margin-top:.45rem;"><strong>Validation:</strong> <code>{{ artifact.validation }}</code></div>
          <ul style="margin:.5rem 0 0 0;padding-left:1rem;font-size:.82rem;">
            <li v-for="item in artifact.artifacts" :key="`${artifact.repo}-${item}`" style="margin:.25rem 0;">
              <code>{{ item }}</code>
            </li>
          </ul>
        </article>
      </div>
    </section>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:1rem;">
      <article style="border:1px solid #dbeafe;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Eval readiness criteria</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="criterion in evalCriteria" :key="criterion.criterion_id" style="margin:.45rem 0;">
            <strong>{{ criterion.criterion_id }}</strong> — {{ criterion.status }}
            <div style="font-size:.8rem;opacity:.62;"><code>{{ criterion.evidence_ref }}</code></div>
          </li>
        </ul>
      </article>

      <article style="border:1px solid #fecaca;border-radius:12px;background:#fff7f7;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;color:#991b1b;">Blocked actions</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="action in blockedActions" :key="action" style="margin:.35rem 0;">
            {{ action }}
          </li>
        </ul>
        <p style="margin:.75rem 0 0 0;font-size:.9rem;color:#7f1d1d;">
          This panel is for non-production evaluation only. It does not enable diagnosis, treatment advice, EHR writes, real clinical data processing, or customer-facing healthcare claims.
        </p>
      </article>
    </section>

    <section style="border:1px dashed #93c5fd;border-radius:12px;padding:.75rem;margin-top:1rem;background:white;">
      <strong>Next allowed action:</strong>
      <code>{{ readiness.next_allowed_action }}</code>
    </section>
  </section>
</template>
