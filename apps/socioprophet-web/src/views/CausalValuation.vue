<script setup lang="ts">
// Dedicated program surface — the GYG causal valuation is its OWN workbench
// surface, not the Studio home. Composes the causal value-driver card with the
// (previously orphaned) location-intelligence map.
import GygCausalValuationCard from '../components/GygCausalValuationCard.vue'
import GygLocationsMapCard from '../components/GygLocationsMapCard.vue'
</script>

<template>
  <GygCausalValuationCard />
  <GygLocationsMapCard />
</template>
