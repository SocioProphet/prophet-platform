# zot — sovereign artifact registry

Self-hosted, login-walled OCI registry at **`registry.socioprophet.ai`**, replacing **both** GHCR
(GitHub) and Google Artifact Registry. Hosts first-party images and pull-through-caches upstream
(`docker.io`/`ghcr.io`/`gcr.io`/`registry.k8s.io`) via the `sync` extension.

## Why zot (not Harbor / JFrog)
Single Go binary, S3-backed, minimal ops — consistent with choosing Gitea over GitLab
(zot : Harbor :: Gitea : GitLab). Covers what mattered (MinIO backend, cosign, Trivy, pull-through)
without Harbor's Postgres+Redis+jobservice fleet. JFrog rejected as heavy/commercial/affiliated.

## Design
- **Storage**: S3 driver → the running `workspace-minio` (`workspace-minio.socioprophet.svc:9000`),
  bucket `zot`. A small RWO PVC (`zot-cache`) holds only the boltdb metadata cache.
- **Auth**: htpasswd bootstrap + `accessControl` login-wall (no anonymous). OIDC later (Phase 4).
- **Deploy**: kustomize (`base` + `overlays/{p0-lab,p1-single-site}`), wired into the live ArgoCD root
  via `deploy/argocd/registry-services.yaml`, sync-wave 1 (after MinIO storage, wave 0).
- **Ingress**: GCE ingress + ManagedCertificate, same pattern as `gitea-sovereign` (`code.socioprophet.ai`).

## Out-of-band prerequisites (NOT committed)
Secrets are created out of band, like `minio-credentials`:

1. **`minio-credentials`** (reused for the S3 backend) — already created in `socioprophet`.
2. **`zot-htpasswd`** — bootstrap `admin` + `ci` users. Create with:
   ```sh
   # bcrypt htpasswd for admin + ci (use strong, stored passwords)
   htpasswd -Bbn admin "<ADMIN_PW>"  > /tmp/zot.htpasswd
   htpasswd -Bbn ci    "<CI_PW>"    >> /tmp/zot.htpasswd
   kubectl create secret generic zot-htpasswd -n socioprophet --from-file=htpasswd=/tmp/zot.htpasswd
   rm /tmp/zot.htpasswd
   ```
   Persist both passwords in the secret manager. `ci` is the identity CI uses to push images.

## Deploy checklist
1. Create the `zot-htpasswd` secret (above).
2. Ensure the `zot` bucket exists in MinIO (create via console/mc if MinIO doesn't auto-create).
3. Merge → ArgoCD syncs `registry-zot`. Get the Ingress IP: `kubectl get ingress -n socioprophet zot-ingress`.
4. Point `registry.socioprophet.ai` A-record at that IP; wait for the ManagedCertificate to go Active.
5. **Verify the LB health path** `/v2/_zot/ready` against the pinned zot version (the one GKE-specific wrinkle).

## Cutover (after zot is Healthy)
- **Pull-through** is on immediately (sync, on-demand) — the cluster can pull any upstream image through zot.
- Push first-party images to zot; repoint `workspace-{mail,smtp,caldav}` overlays + the `build-image`
  pipeline from GHCR/GAR → zot; add a zot pull secret (our own creds). Then mail/caldav go Ready.
- Retire the GAR terraform (`infra/tofu/modules/artifact-registry` + `artifactregistry.*` IAM) and GHCR usage.

## Bootstrap circularity
zot's own image + MinIO + ingress are pulled from upstream on first bring-up (one-time). Once zot is up,
mirror those critical infra images into zot via `sync`, but keep upstream fallback. Never make zot the
*sole* source of the images needed to boot zot/MinIO/ingress.
