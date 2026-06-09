<script setup lang="ts">
import readiness from '../../../../contracts/prophet-mesh/demo/prophet-mesh-runtime-readiness.v0.json'

type SourceBasis = {
  source_id: string
  source_class: string
  classification: string
  notes: string
}

type UpstreamArtifact = {
  repo: string
  ref: string
  artifacts: string[]
  validation: string
}

const runtimePath = readiness.runtime_path
const demoSurface = readiness.demo_surface
const sourceBasis = readiness.source_basis as SourceBasis[]
const upstreamArtifacts = readiness.upstream_artifacts as UpstreamArtifact[]
const controls = Object.entries(runtimePath.controls)

const routeSummary = [
  ['Conductor', runtimePath.conductor_id],
  ['Request', runtimePath.request_id],
  ['Task', runtimePath.task],
  ['Domain', runtimePath.domain],
  ['Selected route', runtimePath.selected_route],
  ['Fallback route', runtimePath.fallback_route],
  ['Policy decision', runtimePath.policy_decision],
  ['Trace status', runtimePath.execution_trace_status]
]

const safetyFlags = [
  ['Production ready', readiness.production_ready],
  ['External action allowed', readiness.external_action_allowed],
  ['Live provider call', readiness.live_provider_call],
  ['Provider secrets required', readiness.provider_secrets_required],
  ['Real user data processing', readiness.real_user_data_processing],
  ['Customer-facing claim', readiness.customer_facing_claim]
]
</script>

<template>
  <section style="border:1px solid #cbd5e1;border-radius:16px;padding:1rem;margin-top:1.5rem;background:#f8fafc;">
    <div style="display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:800;">
          Prophet Mesh runtime readiness
        </div>
        <h2 style="margin:.4rem 0 .35rem 0;font-size:1.35rem;font-weight:800;">
          Governed conductor and choir readout
        </h2>
        <p style="margin:0;opacity:.78;max-width:820px;">
          Fixture-backed readout for the Michael Agent conductor, model-router decision, specialist-agent choir, evidence refs, audit refs, and approval boundary. This panel presents the runtime path only; it does not invoke providers or perform external actions.
        </p>
      </div>
      <div style="border:1px solid #94a3b8;border-radius:999px;background:white;padding:.35rem .65rem;font-size:.85rem;font-weight:800;white-space:nowrap;">
        {{ readiness.readiness_state }}
      </div>
    </div>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:.75rem;margin-top:1rem;">
      <article
        v-for="([label, value]) in safetyFlags"
        :key="label"
        style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.75rem;"
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
      <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Runtime route</h3>
        <dl style="margin:0;display:grid;gap:.5rem;">
          <div v-for="([label, value]) in routeSummary" :key="label">
            <dt style="font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;opacity:.62;font-weight:800;">{{ label }}</dt>
            <dd style="margin:.15rem 0 0 0;font-weight:750;"><code>{{ value }}</code></dd>
          </div>
        </dl>
      </article>

      <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Specialist choir</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="agent in runtimePath.specialist_agents" :key="agent" style="margin:.35rem 0;">
            <code>{{ agent }}</code>
          </li>
        </ul>
        <h4 style="margin:.8rem 0 .35rem 0;font-size:.92rem;">Approval boundary</h4>
        <p style="margin:0;font-size:.9rem;"><code>{{ runtimePath.approval_boundary }}</code></p>
      </article>
    </section>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:1rem;">
      <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Controls</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="([control, enabled]) in controls" :key="control" style="margin:.3rem 0;">
            <strong>{{ control }}</strong> — {{ enabled ? 'true' : 'false' }}
          </li>
        </ul>
      </article>

      <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Evidence and audit</h3>
        <h4 style="margin:.2rem 0 .35rem 0;font-size:.9rem;">Evidence refs</h4>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="ref in runtimePath.evidence_refs" :key="ref" style="margin:.25rem 0;"><code>{{ ref }}</code></li>
        </ul>
        <h4 style="margin:.8rem 0 .35rem 0;font-size:.9rem;">Audit refs</h4>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="ref in runtimePath.audit_refs" :key="ref" style="margin:.25rem 0;"><code>{{ ref }}</code></li>
        </ul>
      </article>
    </section>

    <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;margin-top:1rem;">
      <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Source basis</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.75rem;">
        <article v-for="source in sourceBasis" :key="source.source_id" style="border:1px solid #e2e8f0;border-radius:10px;padding:.7rem;">
          <div style="font-weight:850;">{{ source.source_class }}</div>
          <div style="font-size:.86rem;opacity:.75;margin-top:.2rem;">{{ source.classification }}</div>
          <div style="font-size:.8rem;opacity:.62;margin-top:.35rem;"><code>{{ source.source_id }}</code></div>
          <p style="margin:.45rem 0 0 0;font-size:.9rem;">{{ source.notes }}</p>
        </article>
      </div>
    </section>

    <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;margin-top:1rem;">
      <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Allowed demo views</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="view in demoSurface.allowed_views" :key="view" style="margin:.3rem 0;">{{ view }}</li>
        </ul>
      </article>

      <article style="border:1px solid #fecaca;border-radius:12px;background:#fff7f7;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;color:#991b1b;">Blocked demo views</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="view in demoSurface.blocked_views" :key="view" style="margin:.3rem 0;">{{ view }}</li>
        </ul>
      </article>
    </section>

    <section style="border:1px dashed #94a3b8;border-radius:12px;padding:.75rem;margin-top:1rem;background:white;">
      <strong>Next allowed action:</strong>
      <code>{{ readiness.next_allowed_action }}</code>
    </section>
  </section>
</template>
