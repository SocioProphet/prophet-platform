// Cockpit UI store — the cross-surface glue for the Noetica assistant.
// Holds the dock's open state and the CURRENT SURFACE CONTEXT (what the user is
// looking at), so the assistant is *present and aware* on every page instead of
// a detached chat. Any surface calls setContext() on selection; askAbout() opens
// the dock and asks Noetica about that context in one action.
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { useNoeticaChat } from '../composables/useNoeticaChat';

export interface SurfaceContext {
  surface: string;        // e.g. 'Market Monitor'
  entityLabel?: string;   // e.g. 'SPX · S&P 500'
  detail?: string;        // e.g. '5,259.71 · -1.14%'
  route?: string;         // current path
}

export const useCockpit = defineStore('cockpit', () => {
  const dockOpen = ref(false);
  const graphOpen = ref(false);
  const context = ref<SurfaceContext>({ surface: '' });

  function setContext(c: SurfaceContext) { context.value = c; }
  function openDock() { dockOpen.value = true; }
  function closeDock() { dockOpen.value = false; }
  function toggleDock() { dockOpen.value = !dockOpen.value; }
  function toggleGraph() { graphOpen.value = !graphOpen.value; }
  function closeGraph() { graphOpen.value = false; }

  // One-tap "ask Noetica about what I'm looking at": open the dock + send a
  // context-framed prompt into the shared chat session.
  function askAbout(prompt: string) {
    dockOpen.value = true;
    useNoeticaChat().send(prompt);
  }

  return { dockOpen, graphOpen, context, setContext, openDock, closeDock, toggleDock, toggleGraph, closeGraph, askAbout };
});
