<script setup lang="ts">
// DevSecOps Intelligence Workroom surface — the governed RCA / runtime-parity honesty readout.
// Carried over from Prophet Studio when client-vue became the deployed cockpit (Phase 3): the
// card is unchanged (fetches /api/v1/workroom/report + /api/v1/workroom/runtime-parity-bridge via
// the gateway) so the devsecops-workroom-rca-guards governance guard still holds — it just lives
// on its own route now instead of the old single-page App.vue.
import DevSecOpsWorkroomReportCard from '../components/DevSecOpsWorkroomReportCard.vue';
</script>

<template>
  <section class="sp-page">
    <header class="sp-page-head">
      <h1>DevSecOps Workroom</h1>
      <p>Root-cause analysis, Guardrail bindings, and runtime-parity posture — rendered from the governed fixture contracts, with explicit non-claims.</p>
    </header>
    <DevSecOpsWorkroomReportCard />
  </section>
</template>
