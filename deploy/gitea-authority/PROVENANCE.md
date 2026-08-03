# Vendored gitea-authority closure
Source of truth: `SocioProphet/gitea-sovereign` (`gateway/authority-server.js`,
`core/{local-authority,canonical,nonce-store}.js`). Vendored here so the deploy
can build the image where the estate WIF + Artifact Registry live (the GKE
cluster pulls from AR via its node identity — no imagePullSecret). Re-vendor on
change; the authority logic is zero-dependency and small by design.
