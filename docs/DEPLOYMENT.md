# Deployment

## Dev / local host mode

Run the API and gateway as separate local processes.
Use a shared Unix socket path:

- API: `PLATFORM_RPC_LISTEN=unix:///tmp/socioprophet.sock`
- Gateway: `PLATFORM_RPC_TARGET=unix:///tmp/socioprophet.sock`

## Kubernetes bootstrap mode

Use separate Deployments and connect them over TCP:

- API: `PLATFORM_RPC_LISTEN=tcp://0.0.0.0:9000`
- Gateway: `PLATFORM_RPC_TARGET=tcp://socioprophet-api:9000`

This is the only honest shape while API and gateway remain separate pods.
If we later choose colocated sidecars or a shared pod, UDS can be restored for that profile.
