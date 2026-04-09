# apps/

`apps/` contains deployable runtime services and applications.

## Current runtime surfaces

* `api` — internal TriTRPC bootstrap service
* `gateway` — browser-facing ingress relay
* `socioprophet-web` — portal shell
* `eval-fabric-api` — platform evaluation, observability, and intelligence lane
* `knowledge-reason` — governed claim-evaluation ingress scaffold
* `lampstand` — local-daemon integration target with platform receipt/catalog emission

## Planned imports / promotions

* `agentplane`
* `workspace-controller`
* `identity-prime`
* `hdt-gateway`
* `evidence-receipts`

## Rule

If it is a runtime that ships, runs, scales, or emits receipts, it belongs under `apps/`.
If it is a standard, ontology, mapping pack, or reference model, it stays upstream and is consumed by pin.
