# Runbook — stand up the test mesh and talk to it from Noetica

The shortest real end-to-end: Noetica → `prophet-mesh` conductor → one vLLM seat (T4).
Everything's built; these are the steps that need **your** approval (IAM / GPU spend / control-plane).

## 0. One-time: let Cloud Build build + push images
The project's default SAs were hardened away, so grant the Cloud Build agent its roles once:
```sh
PN=$(gcloud projects describe socioprophet-platform --format='value(projectNumber)')
gcloud beta services identity create --service=cloudbuild.googleapis.com --project socioprophet-platform
for r in roles/cloudbuild.builds.builder roles/artifactregistry.writer roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding socioprophet-platform \
    --member="serviceAccount:${PN}@cloudbuild.gserviceaccount.com" --role="$r" --condition=None
done
```

## 1. Build + push the conductor image  (~2 min)
```sh
cd ~/dev/prophet-mesh
gcloud builds submit --tag us-central1-docker.pkg.dev/socioprophet-platform/socioprophet/prophet-mesh:latest .
```

## 2. Deploy the test mesh — vLLM (T4) + conductor  (GPU spins up here; ~5-15 min for weights)
```sh
kubectl apply -f ~/dev/prophet-platform/deploy/serving/mesh-test-t4.yaml
kubectl -n serving rollout status deploy/mesh-vllm --timeout=20m   # T4 node auto-provisions, model loads
kubectl -n serving rollout status deploy/prophet-mesh --timeout=5m
```

## 3. Reach it from your laptop (no external TLS needed)
```sh
kubectl -n serving port-forward svc/prophet-mesh 8780:8780
```
Then in Noetica → **Settings → Models → Prophet Cloud Mesh**: toggle on, endpoint `http://127.0.0.1:8780/v1`, model `prophet-mesh`, key blank. Chat — the turn routes conductor → vLLM and streams back.

Smoke-test the endpoint directly first:
```sh
curl -s http://127.0.0.1:8780/v1/models | jq              # lists prophet-mesh + seats
curl -s http://127.0.0.1:8780/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"prophet-mesh","messages":[{"role":"user","content":"write a python is_prime(n)"}]}' | jq -r '.choices[0].message.content'
```

## 4. Tear down (stop the GPU spend)
```sh
kubectl delete -f ~/dev/prophet-platform/deploy/serving/mesh-test-t4.yaml
```

---
### Notes / known limits of THIS test
- **One seat, not the choir.** The conductor faithfully proxies to a single T4 vLLM (AWQ 7B). Add more seats to `SEAT_BACKENDS` (each its own vLLM Deployment) to conduct across the 7 families — that needs A100/H100 quota (currently 0; request it in the console).
- **verify→select moat** still runs locally only (Noetica BLOCKER 1). Over-the-mesh neurosymbolic selection belongs in the conductor — a follow-up on `feat/conductor-api`.
- **Demo surface (nginx/web)** is a separate track — blocked on the Argo CD upgrade (v2.13.1 can't diff on GKE 1.35); not needed for this mesh test.
