# apps/

`apps/` contains deployable runtime services and applications.

## Current runtime surfaces

* `api` — internal TriTRPC bootstrap service
* `gateway` — browser-facing ingress relay and thin proxy surface for selected platform readers
* `socioprophet-web` — portal shell
* `eval-fabric-api` — platform evaluation, observability, and intelligence lane
* `knowledge-reason` — governed claim-evaluation ingress scaffold
* `lampstand` — local-daemon integration target with platform receipt/catalog emission
* `evidence-receipts` — platform reader surface for emitted payload/event/receipt artifacts

## Planned imports / promotions

* `agentplane`
* `workspace-controller`
* `identity-prime`
* `hdt-gateway`

## Rule

If it is a runtime that ships, runs, scales, or emits or consumes receipts, it belongs under `apps/`.
If it is a standard, ontology, mapping pack, or reference model, it stays upstream and is consumed by pin.
