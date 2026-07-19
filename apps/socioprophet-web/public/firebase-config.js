// Runtime Firebase web config, injected per environment at DEPLOY time.
//
//   • Empty values (below) → local dev: the auth store's DEV_AUTH_BYPASS supplies a
//     stub signed-in user (dev@localhost), so `npm run dev` works with no project.
//   • Real values → real Google/email login against that Firebase project.
//
// This is the Firebase *web* config (apiKey etc.) — NOT a secret; it ships in client
// code by design. To log in for real, fill the values before `firebase deploy --only
// hosting:app` (dev project first: socioprophet-web-dev-env). CI may overwrite this
// file at deploy so the repo copy stays empty.
window.__FIREBASE_CONFIG__ = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: "",
};
