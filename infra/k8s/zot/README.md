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
2. **`zot-htpasswd`** — bootstrap `admin` + `ci-push` users. Create with:
   ```sh
   # bcrypt htpasswd (use strong, stored passwords)
   htpasswd -Bbn admin   "<ADMIN_PW>"    > /tmp/zot.htpasswd
   htpasswd -Bbn ci-push "<CI_PUSH_PW>" >> /tmp/zot.htpasswd
   kubectl create secret generic zot-htpasswd -n socioprophet --from-file=htpasswd=/tmp/zot.htpasswd
   rm /tmp/zot.htpasswd
   ```
   Persist both passwords in the secret manager.

### `ci-push` — the identity CI uses to push images
`ci-push` holds `read, create, update` and **NOT `delete`** (see the accessControl block in
`base/configmap.yaml`). A publishing pipeline needs to push; it has no reason to be able to erase
production images, so a leaked CI credential cannot empty the registry. Deleting stays with `admin`
and with zot's own retention/gc, which is what actually reclaims space.

**Adding a user to accessControl grants authorization only** — zot authenticates against this
htpasswd file, so a user that is not in it gets a 401 on `podman login` no matter what the policy
says. To add `ci-push` to an EXISTING deployment without disturbing the other users:

```sh
kubectl get secret zot-htpasswd -n socioprophet -o jsonpath='{.data.htpasswd}' | base64 -d > /tmp/zot.htpasswd
htpasswd -Bbn ci-push "<CI_PUSH_PW>" >> /tmp/zot.htpasswd
kubectl create secret generic zot-htpasswd -n socioprophet \
  --from-file=htpasswd=/tmp/zot.htpasswd --dry-run=client -o yaml | kubectl apply -f -
rm /tmp/zot.htpasswd
kubectl rollout restart deployment/zot -n socioprophet    # zot does NOT hot-reload
```

**Verify the credential locally before putting it in CI** — a wrong password is a 401 you would
otherwise discover as a red pipeline:

```sh
podman login registry.socioprophet.ai -u ci-push
```

Then set it once as an **org** secret (one credential, one rotation point — never a copy per repo):

```sh
gh secret set ZOT_CI_USERNAME --org SocioProphet --visibility selected \
  --repos prophet-platform,sociosphere --body ci-push
gh secret set ZOT_CI_PASSWORD --org SocioProphet --visibility selected \
  --repos prophet-platform,sociosphere          # no --body → interactive paste, stays out of shell history
```

**Rotation** is ordered and needs a restart: regenerate the htpasswd entry → apply the secret →
`kubectl rollout restart deployment/zot` → re-paste the org secret. Doing GitHub first breaks CI;
doing zot first breaks CI. For zero downtime add a second user, cut CI over, then drop the old one.

> Follow-up (not done here): `ci` and `github-ci` still hold `delete`. Once every pipeline is on
> `ci-push`, demote or remove them so no CI identity can delete. Left alone in this change because
> prophet-platform's image pipeline is actively publishing with them.

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
