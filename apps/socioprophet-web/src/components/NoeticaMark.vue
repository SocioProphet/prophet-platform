<template>
  <!-- The Noetica identity glyph: an italic serif "N" with a subscript "0" (N₀).
       Mirrors ~/dev/Noetica components/brand/NoeticaMark.tsx so the cockpit's
       Noetica surface is recognizably the same product. Inherits currentColor. -->
  <svg class="nmark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <text class="nmark-n" x="3" y="17.5">N</text>
    <text class="nmark-0" x="14.5" y="20.5">0</text>
  </svg>
</template>

<script setup lang="ts"></script>

<style scoped>
.nmark { display: block; width: 100%; height: 100%; }
.nmark-n {
  font-family: Georgia, 'Times New Roman', serif;
  font-style: italic;
  font-weight: 600;
  font-size: 19px;
  fill: currentColor;
}
.nmark-0 {
  font-family: Georgia, 'Times New Roman', serif;
  font-style: italic;
  font-weight: 600;
  font-size: 9.5px;
  fill: currentColor;
}
</style>
