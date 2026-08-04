# Retrospective — "is this all pure IaC with all dependencies accounted for in the registry?"

**Date:** 2026-08-04 · **Trigger:** the question, asked before building on top of the
catalog/masking work · **Answer: no.**

The estate pins what it **deploys**. It does not pin what it **builds from**. Every
conclusion below is measured, not estimated, and the commands are given so each can be
re-run.

---

## 1. What was already right

Worth stating first, because the gap is narrower than "we have no supply-chain discipline":

- `tools/preflight_deploy_contract.py` is a strong, six-check gate: no moving tags, no
  omitted tags, no un-owned foreign registries, with a **self-tightening ratchet** whose
  entries fail the build once they stop violating. This retrospective's gate is modelled on
  it directly.
- Deployed images are sha-pinned by `gitops-promote`.
- A sovereign OCI registry (zot, MinIO-backed) exists and serves cosign-signed first-party
  images.
- IaC is real: `infra/terraform` (capability tree) and `infra/tofu` (cloud envs), with
  `workspace-terraform-validate.yml` running `fmt -check -recursive` + `validate`.
- The service chart **does** plumb `config` / `secretEnv` / `extraEnv` into the pod spec.

## 2. Every failure found

| # | Failure | Measurement | Severity |
|---|---|---|---|
| F1 | **No Dockerfile digest-pins its base image** | 51 of 53 `apps/*/Dockerfile` use a moving tag — `python:3.12-slim`, `node:20-alpine`, `golang:1.25-alpine`, `rust:1-bookworm`, `pytorch/pytorch:2.5.1-…` | High |
| F2 | **Python dependencies are ranges, not pins** | 14 of 38 `apps/*/requirements.txt` carry `>=` ranges with no lockfile. `fastapi>=0.110,<1` resolves to **0.141.1** today — 31 minor versions of drift the range concealed | High |
| F3 | **`cryptography>=42.0` unbounded on compute-gateway** | The service that mounts the masking PDP — the one whose entire claim is that its cryptographic behaviour is provable — floats its crypto library | High |
| F4 | **No SBOM for any app** | Estate-wide search returns only `apps/lattice-studio/uv.lock` | Medium |
| F5 | **Base images bypass the sovereign registry** | `FROM python:3.12-slim` pulls Docker Hub directly rather than zot's pull-through cache. **0 of 54** Dockerfiles reference `registry.socioprophet.ai`. The de-Google lever exists and is unused at build time | **High — corrected 2026-08-04** |
| F6 | **PyPI is an unmediated external dependency** | zot mirrors OCI artifacts, not Python packages; `pip install` at build time reaches PyPI with no mirror and (until now) no hashes | Medium |
| F7 | **The masking PDP has no IaC configuration** | `GATEWAY_MASKING_POLICY` appears nowhere under `deploy/`. Not a missing mechanism — `extraEnv`/`secretEnv` exist — an **unused** one. The moat is code that is switched off | High |
| F8 | **Spec-repo validators install unpinned at run time** | `sourceos-spec` and `prophet-core-catalog` Makefiles run `python3 -m pip install --user jsonschema >/dev/null` — unpinned, network-dependent, mutating user site-packages, and silencing its own failure output | Medium |

### The shape of it

A sha-pinned image tag is a reproducible **identifier**, not a reproducible **build**.
Rebuilding `sha-ba0c3cbb…` today and in six months produces different software under the
same name, and no artifact anywhere records which dependency closure the running image
actually contains. The deploy gate proves the cluster runs what GitOps says. Nothing proved
what that image was made of.

## 3. Process failures in this session

Recorded because the question was "document *every* failure," and these are the ones that
would otherwise go unlogged.

| # | What happened | Why it happened | What caught it |
|---|---|---|---|
| P1 | Reported "`make validate` mutates committed datasets" in prophet-core-catalog. **False.** | Observed a dirty file *after* running `make validate` and inferred causation without checking whether it was dirty *before*. A pristine checkout was already dirty — the real cause was a case-collision. | Testing the claim before fixing it. Withdrawn in prophet-core-catalog#37 |
| P2 | Asserted the service chart had no `env` plumbing, which would have blocked F7. **False.** | Grepped `_helpers.tpl`, found nothing, concluded. The plumbing lives in `_podtemplate.tpl`. | Rendering the chart instead of trusting grep |
| P3 | First version of the healer wrote a hash-pinned `requirements.lock` while leaving the Dockerfile installing from `requirements.txt` — an **inert** lock that looks like a fix | Verified the command succeeded rather than the artifact worked | Checking whether the build actually consumes the lock |
| P4 | Same healer left absolute scratchpad paths in the generated lock header | Ran `uv` with absolute paths from the repo root | Reading the generated file |

P1 and P3 are the same error twice: **trusting that an action succeeded instead of checking
what it produced.** That is the estate's own `verify-artifact-not-command` rule, and it was
broken by the person invoking it.

## 4. The automated self-healing improvement

`tools/preflight_build_contract.py` — the build-layer sibling of the deploy contract.

### Detect

1. Every first-party Dockerfile digest-pins each base image (multi-stage `AS` aliases are
   correctly not treated as pulls).
2. Every app's dependencies are hash-pinned — satisfied either by a fully-`==` requirements
   file, **or** by a `requirements.lock` that the Dockerfile actually installs under
   `--require-hashes`.
3. **Ratchet integrity** — an entry that stops violating fails the gate until it is deleted.

### Heal — the part that makes this more than another detector

`--heal [APP...]` performs the fix rather than describing it:

- resolves each moving base tag to its current digest via `docker manifest inspect`
  (registry API; needs no daemon) and rewrites the `FROM` line;
- compiles the requirements range set into a hash-pinned lock via `uv pip compile
  --generate-hashes`;
- **rewires the Dockerfile** to `COPY requirements.lock` and `pip install --require-hashes`,
  because a lock the build never reads is decoration (see P3).

Detect-without-heal is what leaves 65 violations sitting for a year. The remediation is one
command per service.

### Ratchet, not big-bang

65 pre-existing violations are deferred in `tools/build_contract_ratchet.json` with a per-entry
reason and heal command. The gate is green on day one and **rejects every new violation**. A
gate that fails 61 times on introduction gets disabled; a ratchet converges. It only shrinks —
a healed entry left in the file fails the build until removed, so a fixed violation can never
silently re-permit itself.

### Proven to bite

Both directions, verified:

- a new service with `FROM python:3.12-slim` + `requests>=2` → **exit 1**, both violations named;
- `apps/catalog-gateway/Dockerfile` healed but left in the ratchet → **exit 1**, "now
  digest-pinned but still in the ratchet — remove it".

### Proven to work

`catalog-gateway` and `compute-gateway` are healed in this change — the two services carrying
the masking moat. The resulting lock installs cleanly under `--require-hashes` into a clean
interpreter (`fastapi 0.141.1`, `uvicorn 0.52.1`). Violations 69 → 65; conformant artifacts
22 → 26.

**Not proven here:** the container image build itself. No Docker daemon was available in this
environment, so `docker build` could not run. CI is the artifact-level proof and must be
watched on this PR — I am not claiming a build I did not observe.

## 5. What this does not fix

Named so they are not assumed closed:

- **F4 (SBOM)** — pinning makes an SBOM derivable but does not emit one. Next: generate
  CycloneDX at build time from the lock and attach it to the image as an OCI artifact.
- **F5/F6 (sovereign supply)** — pins make external fetches *reproducible*, not *sovereign*.
  Base images still come from Docker Hub, packages still from PyPI. Next: route base images
  through zot `sync`, then stand up a PyPI mirror.
- **F7 (masking policy in IaC)** — addressed separately, since it is a values change rather
  than a supply-chain one.
- **F8 (spec-repo validators)** — different repos; needs the same treatment there.
- The remaining **65 ratcheted violations**. The ratchet makes the debt visible and
  non-increasing; it does not pay it down.


---

## Correction (2026-08-04, same day)

**F5 was under-rated and I then made it worse.**

Rated Medium and treated as hygiene. It is High: this estate's registry *is* zot, which runs
`sync` pull-through for docker.io / ghcr.io / gcr.io / registry.k8s.io precisely so no build
depends on a hyperscaler registry. CI already **pushes** there. The pull side never moved —
**0 of 54 Dockerfiles reference the sovereign registry.**

Then I compounded it. Told the pins were blocked by Docker Hub's 100/hour limit, I treated that
rate limit as an environmental constraint to design around and digest-pinned 13 base images
**against Docker Hub** — entrenching a dependency the estate deliberately does not have. The
rate limit was not a constraint. It was the symptom of using the wrong registry, and I optimised
against the symptom.

I also considered `mirror.gcr.io` as a workaround and rejected it for digest-provenance reasons.
That reasoning was sound and the framing was still wrong: the question was never which
*hyperscaler* mirror to trust, it was why a build was reaching a hyperscaler at all.

**Fixed by making it enforced rather than intended:** the build contract now refuses any
first-party Dockerfile whose base images are not pulled through `registry.socioprophet.ai`,
ratcheted at the current 54 so it blocks new violations immediately. `--heal` repoints refs at
zot and **re-resolves each digest from zot** — a digest is only meaningful relative to the
registry serving it, so carrying a Docker Hub digest onto a zot ref would assert a
correspondence nobody verified.

The heal needs `ZOT_USERNAME`/`ZOT_PASSWORD`; CI holds `ZOT_CI_USERNAME`/`ZOT_CI_PASSWORD`
already.
