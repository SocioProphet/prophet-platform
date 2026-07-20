// Runtime Firebase web config, injected per environment at DEPLOY time.
//
//   • Empty values → local dev: the auth store's DEV_AUTH_BYPASS supplies a
//     stub signed-in user (dev@localhost), so `npm run dev` works with no project.
//   • Real values (below) → real Google/email login against the socioprophet-web
//     Firebase project. hasConfig=true flips the router guard to real auth, so an
//     unauthenticated visitor lands on /login (Google + email/password) and only
//     reaches the cockpit after signing in.
//
// This is the Firebase *web* config (apiKey etc.) — NOT a secret; it ships in client
// code by design (these are the authoritative values served at
// https://socioprophet-web.firebaseapp.com/__/firebase/init.json).
//
// authDomain stays on the firebaseapp.com handler domain: the OAuth handler
// (/__/auth/*) is served there, so sign-in works from any *authorized* origin
// (app.socioprophet.ai / app.socioprophet.com). Those origins must be listed under
// Firebase Console → Authentication → Settings → Authorized domains, else
// signInWithPopup fails with auth/unauthorized-domain.
window.__FIREBASE_CONFIG__ = {
  apiKey: "AIzaSyCBYZl-mFBeDizhOzH2GePn-xJsd26g1O0",
  authDomain: "socioprophet-web.firebaseapp.com",
  projectId: "socioprophet-web",
  storageBucket: "socioprophet-web.firebasestorage.app",
  messagingSenderId: "392608809931",
  appId: "1:392608809931:web:fcc04db9c0fdf782662c4e",
};
