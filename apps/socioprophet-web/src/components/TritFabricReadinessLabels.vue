<script setup lang="ts">
// Vendored copy of contracts/integrations/tritfabric-ui-labels.v0.json — the client-vue image
// build only copies apps/socioprophet-web, so a repo-root import would break the Docker build.
// The root contract is kept in sync and is what validate_tritfabric_ui_component.py checks.
import labelContract from '../contracts/tritfabric-ui-labels.v0.json'

type Label = {
  surface_id: string
  display_label: string
  status_label: string
  must_show: string[]
  forbidden_badges: string[]
}

const labels = labelContract.labels as Label[]
const claimBoundary = labelContract.claim_boundary
</script>

<template>
  <section style="border:1px solid #e2e8f0;border-radius:16px;padding:1rem;margin-top:1.5rem;">
    <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:700;">
      TritFabric readiness labels
    </div>
    <h2 style="margin:.4rem 0 0.6rem 0;font-size:1.4rem;font-weight:700;">
      Governed product-consumption surfaces
    </h2>
    <p style="margin:0 0 1rem 0;opacity:.82;">
      Label contract for displaying TritFabric-derived Community Learning, Network Atlas, model-card evidence, and Serve readiness surfaces without implying runtime authority.
    </p>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.75rem;margin-bottom:1rem;">
      <article v-for="label in labels" :key="label.surface_id" style="border:1px solid #e2e8f0;border-radius:12px;padding:.75rem;">
        <div style="font-size:12px;text-transform:uppercase;opacity:.65;font-weight:700;">{{ label.status_label }}</div>
        <h3 style="margin:.35rem 0 .5rem 0;font-size:1rem;font-weight:700;">{{ label.display_label }}</h3>
        <div style="font-size:.8rem;opacity:.62;margin-bottom:.5rem;">{{ label.surface_id }}</div>
        <section>
          <div style="font-size:.82rem;font-weight:700;margin-bottom:.25rem;">Must show</div>
          <ul style="margin:0 0 .75rem 0;padding-left:1rem;">
            <li v-for="item in label.must_show" :key="`${label.surface_id}-must-${item}`" style="margin:.25rem 0;">{{ item }}</li>
          </ul>
        </section>
        <section>
          <div style="font-size:.82rem;font-weight:700;margin-bottom:.25rem;">Forbidden badges</div>
          <ul style="margin:0;padding-left:1rem;">
            <li v-for="item in label.forbidden_badges" :key="`${label.surface_id}-forbidden-${item}`" style="margin:.25rem 0;">{{ item }}</li>
          </ul>
        </section>
      </article>
    </div>

    <section style="border:1px dashed #cbd5e1;border-radius:12px;padding:.75rem;">
      <div style="font-size:.82rem;font-weight:700;margin-bottom:.25rem;">Claim boundary</div>
      <p style="margin:0;opacity:.78;">{{ claimBoundary }}</p>
    </section>
  </section>
</template>
