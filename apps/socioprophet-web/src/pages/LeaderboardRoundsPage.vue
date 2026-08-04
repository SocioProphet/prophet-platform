<script setup lang="ts">
import LeaderboardRoundsBoard from '../components/LeaderboardRoundsBoard.vue'
</script>

<template>
  <section class="sp-page">
    <header class="sp-page-head">
      <h1>Eval Leaderboard</h1>
      <p class="sp-page-desc">
        Live rounds board — CLOSED (comparable) and OPEN (novel methods) divisions, governed by the
        leaderboard-round contract.
      </p>
    </header>
    <LeaderboardRoundsBoard />
  </section>
</template>
