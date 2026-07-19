<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../stores/auth";

const auth = useAuth();
const router = useRouter();
const email = ref(""); const pw = ref(""); const err = ref(""); const busy = ref(false);

const go = () => router.push("/");
async function run(fn: () => Promise<unknown>) {
  err.value = ""; busy.value = true;
  try { await fn(); go(); }
  catch (e: any) { err.value = e?.message ? String(e.message).replace(/^Firebase:\s*/, "") : "Sign-in failed. Try again."; }
  finally { busy.value = false; }
}
const google = () => run(() => auth.signInGoogle());
const signin = () => run(() => auth.signInEmail(email.value, pw.value));
const register = () => run(() => auth.registerEmail(email.value, pw.value));
</script>

<template>
  <div class="login">
    <form class="login-card" @submit.prevent="signin">
      <div class="login-brand">SocioProphet</div>
      <h1 class="login-title">Sign in</h1>
      <p class="login-sub">Your governed intelligence cockpit — maps, markets, law, people, and the Noetica agent, under one policy plane.</p>

      <button class="login-google" type="button" :disabled="busy" @click="google">
        <span class="login-g" aria-hidden="true">G</span>
        Continue with Google
      </button>

      <div class="login-or"><span>or</span></div>

      <label class="login-field">
        <span>Email</span>
        <input v-model="email" type="email" autocomplete="email" placeholder="you@org.com" :disabled="busy" />
      </label>
      <label class="login-field">
        <span>Password</span>
        <input v-model="pw" type="password" autocomplete="current-password" placeholder="••••••••" :disabled="busy" />
      </label>

      <div class="login-actions">
        <button class="login-btn primary" type="submit" :disabled="busy">{{ busy ? "…" : "Sign in" }}</button>
        <button class="login-btn ghost" type="button" :disabled="busy" @click="register">Create account</button>
      </div>

      <p v-if="err" class="login-err" role="alert">{{ err }}</p>
    </form>
  </div>
</template>

<style scoped>
.login { height: 100%; min-height: 0; display: grid; place-items: center; padding: 2rem 1rem; background: var(--bg); color: var(--text); overflow-y: auto; }
.login-card { width: 100%; max-width: 380px; display: flex; flex-direction: column; gap: 0.75rem; border: 1px solid var(--line-2); border-radius: 16px; background: var(--surface); padding: 2rem 1.9rem 1.9rem; box-shadow: 0 20px 60px -30px rgba(0, 0, 0, 0.7); }
.login-brand { font-size: 0.66rem; text-transform: uppercase; letter-spacing: 0.18em; color: var(--accent); font-weight: 600; }
.login-title { margin: 0.1rem 0 0; font-size: 1.55rem; font-weight: 660; letter-spacing: -0.01em; }
.login-sub { margin: 0 0 0.4rem; font-size: 0.82rem; line-height: 1.5; color: var(--text-3); }

.login-google { display: flex; align-items: center; justify-content: center; gap: 0.55rem; width: 100%; padding: 0.65rem; border: 1px solid var(--line-2); border-radius: 10px; background: var(--surface-2, #1b1e25); color: var(--text); font-size: 0.9rem; font-weight: 550; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
.login-google:hover:not(:disabled) { border-color: var(--text-3); background: rgba(255, 255, 255, 0.03); }
.login-google:disabled { opacity: 0.55; cursor: default; }
.login-g { display: grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; background: #fff; color: #4285f4; font-weight: 800; font-size: 0.72rem; font-family: Georgia, serif; }

.login-or { display: flex; align-items: center; gap: 0.6rem; color: var(--text-3); font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.08em; margin: 0.15rem 0; }
.login-or::before, .login-or::after { content: ""; flex: 1; height: 1px; background: var(--line); }

.login-field { display: flex; flex-direction: column; gap: 0.28rem; }
.login-field span { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-3); }
.login-field input { width: 100%; padding: 0.55rem 0.65rem; border: 1px solid var(--line-2); border-radius: 9px; background: var(--bg); color: var(--text); font-size: 0.88rem; transition: border-color 0.15s, box-shadow 0.15s; }
.login-field input::placeholder { color: var(--text-3); opacity: 0.6; }
.login-field input:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft, rgba(216, 162, 80, 0.18)); }

.login-actions { display: grid; grid-template-columns: 1fr auto; gap: 0.5rem; margin-top: 0.55rem; }
.login-btn { padding: 0.6rem 0.9rem; border-radius: 10px; font-size: 0.88rem; font-weight: 600; cursor: pointer; border: 1px solid transparent; transition: filter 0.15s, background 0.15s; }
.login-btn:disabled { opacity: 0.6; cursor: default; }
.login-btn.primary { background: var(--accent); color: #14110a; } .login-btn.primary:hover:not(:disabled) { filter: brightness(1.06); }
.login-btn.ghost { background: transparent; border-color: var(--line-2); color: var(--text-2); } .login-btn.ghost:hover:not(:disabled) { border-color: var(--text-3); color: var(--text); }

.login-err { margin: 0.35rem 0 0; font-size: 0.76rem; color: var(--down); background: rgba(240, 101, 106, 0.1); border: 1px solid rgba(240, 101, 106, 0.3); border-radius: 8px; padding: 0.5rem 0.65rem; }
</style>
