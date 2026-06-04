<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

type EvidenceItem = {
  evidence_ref: string
  evidence_type: string
  producer: string
  summary: string
}

type RcaClaim = {
  claim_id: string
  claim_status: string
  confidence: string
  statement: string
}

type ActionGrant = {
  action_class: string
  approval_required: boolean
  grant_id: string
  scope: string
  status: string
}

type GuardrailBinding = {
  grant_ref: string
  guardrail_fixture_ref: string
  guardrail_expected_decision: string
  binding_status: string
}

type RemediationPlan = {
  plan_id: string
  plan_status: string
  risk_class: string
  summary: string
}

type WorkroomReport = {
  report_id: string
  workroom: {
    workroom_id: string
    lane: string
    runtime_parity_level: string
    incident_ref: string
    topology_ref: string
    blast_radius_ref: string
  }
  event: {
    event_type: string
    status: string
    decision_state: string
    summary: string
  }
  evidence: EvidenceItem[]
  rca_claims: RcaClaim[]
  gaia_blast_radius: {
    radius_status: string
    affected_node_refs: string[]
    candidate_consumer_refs: string[]
    confidence: string
  }
  action_grants: ActionGrant[]
  guardrail_decision_bindings: {
    action_grant_bindings: GuardrailBinding[]
  }
  remediation_plans: RemediationPlan[]
  non_claims: string[]
}

type RuntimeParityBridge = {
  bridge_id: string
  decision_state: string
  observed_evidence: {
    fogstack_parity_status: string
    fogstack_parity_target: string
    svf_adapter_readiness_status: string
    svf_adapter_merge_readiness: string
    fogstack_checked_lanes: Record<string, string>
  }
  certified_claims: string[]
  non_certified_claims: string[]
  next_required_evidence: string[]
  non_claims: string[]
}

const report = ref<WorkroomReport | null>(null)
const runtimeBridge = ref<RuntimeParityBridge | null>(null)
const loading = ref(false)
const error = ref('')

async function loadReport() {
  loading.value = true
  error.value = ''
  try {
    const [reportRes, bridgeRes] = await Promise.all([
      fetch('/api/v1/workroom/report'),
      fetch('/api/v1/workroom/runtime-parity-bridge')
    ])
    if (!reportRes.ok) throw new Error(`report request failed: ${reportRes.status}`)
    if (!bridgeRes.ok) throw new Error(`runtime parity bridge request failed: ${bridgeRes.status}`)
    report.value = await reportRes.json()
    runtimeBridge.value = await bridgeRes.json()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'report request failed'
    report.value = null
    runtimeBridge.value = null
  } finally {
    loading.value = false
  }
}

const confirmedClaims = computed(() =>
  report.value?.rca_claims.filter((claim) => claim.claim_status === 'confirmed_causal_claim') ?? []
)

const executedPlans = computed(() =>
  report.value?.remediation_plans.filter((plan) => plan.plan_status === 'executed') ?? []
)

const bridgeLaneEntries = computed(() =>
  Object.entries(runtimeBridge.value?.observed_evidence.fogstack_checked_lanes ?? {})
)

onMounted(loadReport)
</script>

<template>
  <section style="border:1px solid #cbd5e1;border-radius:16px;padding:1rem;margin-top:1.5rem;background:#f8fafc;">
    <div style="display:flex;gap:.75rem;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:700;">
          DevSecOps Intelligence Workroom
        </div>
        <h2 style="margin:.4rem 0 .35rem 0;font-size:1.35rem;font-weight:750;">Fixture report surface</h2>
        <p style="margin:0;opacity:.78;max-width:760px;">
          Deterministic Workroom report rendered from fixture contracts. This surface separates evidence, claims, topology context, Guardrail bindings, remediation candidates, runtime parity bridge posture, and non-claims.
        </p>
      </div>
      <button @click="loadReport" style="padding:.45rem .75rem;border:1px solid #94a3b8;border-radius:8px;background:white;white-space:nowrap;">
        {{ loading ? 'Loading…' : 'Reload' }}
      </button>
    </div>

    <p v-if="error" style="border:1px solid #fecaca;background:#fef2f2;border-radius:10px;padding:.75rem;margin:1rem 0 0 0;color:#991b1b;">
      {{ error }}
    </p>

    <div v-if="report" style="margin-top:1rem;display:grid;gap:1rem;">
      <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Event state</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.6rem;">
          <div><strong>Lane</strong><br><code>{{ report.workroom.lane }}</code></div>
          <div><strong>Parity</strong><br><code>{{ report.workroom.runtime_parity_level }}</code></div>
          <div><strong>Event</strong><br><code>{{ report.event.event_type }}</code></div>
          <div><strong>Decision</strong><br><code>{{ report.event.decision_state }}</code></div>
        </div>
        <p style="margin:.75rem 0 0 0;">{{ report.event.summary }}</p>
      </section>

      <section v-if="runtimeBridge" style="border:1px solid #cbd5e1;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Runtime parity bridge</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.6rem;">
          <div><strong>Decision</strong><br><code>{{ runtimeBridge.decision_state }}</code></div>
          <div><strong>FogStack parity</strong><br><code>{{ runtimeBridge.observed_evidence.fogstack_parity_status }}</code></div>
          <div><strong>SVF adapter</strong><br><code>{{ runtimeBridge.observed_evidence.svf_adapter_readiness_status }}</code></div>
          <div><strong>Merge readiness</strong><br><code>{{ runtimeBridge.observed_evidence.svf_adapter_merge_readiness }}</code></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin-top:.75rem;">
          <article style="border:1px solid #e2e8f0;border-radius:10px;padding:.65rem;">
            <h4 style="margin:0 0 .45rem 0;">Checked lanes</h4>
            <ul style="margin:0;padding-left:1rem;">
              <li v-for="([lane, state]) in bridgeLaneEntries" :key="lane" style="margin:.3rem 0;">
                <code>{{ lane }}</code> — {{ state }}
              </li>
            </ul>
          </article>
          <article style="border:1px solid #e2e8f0;border-radius:10px;padding:.65rem;">
            <h4 style="margin:0 0 .45rem 0;">Not certified</h4>
            <ul style="margin:0;padding-left:1rem;">
              <li v-for="claim in runtimeBridge.non_certified_claims" :key="claim" style="margin:.3rem 0;">{{ claim }}</li>
            </ul>
          </article>
        </div>
      </section>

      <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;">
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Evidence</h3>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="item in report.evidence" :key="item.evidence_ref" style="margin:.45rem 0;">
              <strong>{{ item.evidence_type }}</strong> — {{ item.summary }}
              <div style="font-size:.82rem;opacity:.65;"><code>{{ item.evidence_ref }}</code></div>
            </li>
          </ul>
        </article>

        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">RCA claims</h3>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="claim in report.rca_claims" :key="claim.claim_id" style="margin:.45rem 0;">
              <strong>{{ claim.claim_status }}</strong> / {{ claim.confidence }} — {{ claim.statement }}
            </li>
          </ul>
          <p v-if="confirmedClaims.length === 0" style="margin:.75rem 0 0 0;font-size:.9rem;opacity:.72;">
            No confirmed causal claim is present in the fixture report.
          </p>
        </article>
      </section>

      <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;">
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">GAIA blast radius</h3>
          <p style="margin:0 0 .5rem 0;"><strong>Status:</strong> <code>{{ report.gaia_blast_radius.radius_status }}</code></p>
          <p style="margin:.35rem 0;"><strong>Affected:</strong> {{ report.gaia_blast_radius.affected_node_refs.join(', ') }}</p>
          <p style="margin:.35rem 0;"><strong>Candidate consumers:</strong> {{ report.gaia_blast_radius.candidate_consumer_refs.join(', ') }}</p>
          <p style="margin:.35rem 0;"><strong>Confidence:</strong> {{ report.gaia_blast_radius.confidence }}</p>
        </article>

        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Action safety</h3>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="grant in report.action_grants" :key="grant.grant_id" style="margin:.45rem 0;">
              <strong>{{ grant.action_class }}</strong> — <code>{{ grant.status }}</code>
              <span v-if="grant.approval_required"> / approval required</span>
            </li>
          </ul>
        </article>
      </section>

      <section style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
        <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Guardrail decision bindings</h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.75rem;">
          <div v-for="binding in report.guardrail_decision_bindings.action_grant_bindings" :key="binding.grant_ref" style="border:1px solid #e2e8f0;border-radius:10px;padding:.65rem;">
            <div><strong>{{ binding.binding_status }}</strong> — expected <code>{{ binding.guardrail_expected_decision }}</code></div>
            <div style="font-size:.82rem;opacity:.7;margin-top:.35rem;"><code>{{ binding.grant_ref }}</code></div>
          </div>
        </div>
      </section>

      <section style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;">
        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Remediation</h3>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="plan in report.remediation_plans" :key="plan.plan_id" style="margin:.45rem 0;">
              <strong>{{ plan.risk_class }}</strong> / <code>{{ plan.plan_status }}</code> — {{ plan.summary }}
            </li>
          </ul>
          <p v-if="executedPlans.length === 0" style="margin:.75rem 0 0 0;font-size:.9rem;opacity:.72;">
            No remediation is executed by this fixture report.
          </p>
        </article>

        <article style="border:1px solid #e2e8f0;border-radius:12px;background:white;padding:.85rem;">
          <h3 style="margin:0 0 .6rem 0;font-size:1rem;">Non-claims</h3>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="item in report.non_claims" :key="item" style="margin:.35rem 0;">{{ item }}</li>
          </ul>
        </article>
      </section>
    </div>
  </section>
</template>
