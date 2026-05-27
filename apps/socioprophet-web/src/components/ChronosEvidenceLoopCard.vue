<script setup lang="ts">
import readout from '../../../contracts/chronos-evidence-loop/customer-readout.v0.json'
</script>

<template>
  <section style="border:1px solid #e2e8f0;border-radius:16px;padding:1rem;margin-top:1.5rem;">
    <div style="font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.65;font-weight:700;">
      Governed Intelligence Rollout
    </div>
    <h2 style="margin:.4rem 0 0.6rem 0;font-size:1.4rem;font-weight:700;">
      {{ readout.title }}
    </h2>
    <p style="margin:0 0 1rem 0;opacity:.82;">
      {{ readout.summary }}
    </p>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.75rem;margin-bottom:1rem;">
      <article v-for="plane in readout.carrier_planes" :key="plane.repo" style="border:1px solid #e2e8f0;border-radius:12px;padding:.75rem;">
        <div style="font-size:12px;text-transform:uppercase;opacity:.65;font-weight:700;">{{ plane.plane }}</div>
        <div style="font-weight:700;margin-top:.25rem;">{{ plane.repo }}</div>
        <div style="font-size:.92rem;opacity:.78;margin-top:.35rem;">{{ plane.carrier }}</div>
        <div style="font-size:.8rem;opacity:.62;margin-top:.45rem;">Merged {{ plane.merged_ref }}</div>
      </article>
    </div>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;">
      <section>
        <h3 style="margin:0 0 .5rem 0;font-size:1rem;">Proof points</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="item in readout.proof_points" :key="item" style="margin:.3rem 0;">{{ item }}</li>
        </ul>
      </section>
      <section>
        <h3 style="margin:0 0 .5rem 0;font-size:1rem;">Non-claims</h3>
        <ul style="margin:0;padding-left:1rem;">
          <li v-for="item in readout.non_claims" :key="item" style="margin:.3rem 0;">{{ item }}</li>
        </ul>
      </section>
    </div>
  </section>
</template>
