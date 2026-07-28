# noetica-impair (vendored)

GPU batch image for the impairment rig. **Canonical source is
[SocioProphet/noetica-impair](https://github.com/SocioProphet/noetica-impair)** — this
directory is a vendored copy that exists so `images.yml` has a build context, matching
the pattern used by `apps/reasoning-failure-runner`.

## Why it is vendored rather than cloned at build time

Per the estate rule, images ship through this repo's CI and must not be gated on org
secrets or on network access to another repo at build time. A vendored context builds
from what is committed here, so the image is reproducible from this tree alone.

## It is a Job, not a Deployment

No port, no `/healthz`, no Service. Configuration arrives as environment variables (see
`src/noetica_impair/planes/base.py::RunJob.to_env`). `gitops-promote` therefore has no
values file to rewrite for it — **reference the image by an explicit `sha-<commit>` tag
from the run planes**, never `:latest`, or a fix will never roll out under
`imagePullPolicy: IfNotPresent`.

## Weights are never fetched at runtime

The Dockerfile sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` deliberately — the
rig's invariant 0.6 is local-only, no implicit downloads. Weights must be pre-staged
and mounted; the container will not reach out for them.

## Keeping this copy honest

When the canonical repo changes, re-copy `Dockerfile`, `requirements.txt`,
`pyproject.toml`, `src/` and `tests/`. The vendored tests are included so this build
context can be verified in isolation rather than trusted.
