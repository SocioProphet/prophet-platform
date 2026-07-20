// Runtime Firebase web config — injected at DEPLOY time, NOT committed here.
//
//   • Empty values (this repo copy) → local dev: the auth store's DEV_AUTH_BYPASS
//     supplies a stub signed-in user (dev@localhost), so `npm run dev` works with no
//     project. This is also what ships in the image layer (so nothing lands in git or
//     the image).
//   • In-cluster, this file is OVERLAID by a ConfigMap-mounted copy holding the real
//     socioprophet-web Firebase web config (see deploy/values/socioprophet-web.yaml
//     `extraFileMounts` → configMap `socioprophet-web-firebase-config`). hasConfig=true
//     then flips the router guard to real auth: an unauthenticated visitor lands on
//     /login (Google + email/password), then the cockpit.
//
// Why injected, not committed: the Firebase *web* config (apiKey etc.) is public by
// design — it ships in the browser bundle and Google serves it at
// /__/firebase/init.json — but committing it trips automated secret scanners and puts
// it in git history for no benefit. The ConfigMap lives in the cluster, out of git.
// The key's real protection is API-key restrictions + Firebase Security Rules +
// Auth authorized domains, not secrecy of this string.
window.__FIREBASE_CONFIG__ = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: "",
};
