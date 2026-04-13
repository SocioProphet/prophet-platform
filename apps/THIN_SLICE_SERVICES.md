# Thin-Slice Services Overview

This document provides an overview of the **thin-slice services** that will be the first executable truth path in the Prophet Platform local development environment.

These services are the minimal set required to achieve:

1. Build local images
2. Bring up minimal services
3. Train models
4. Register and promote models
5. Perform inference
6. Tear down the environment

## Services to be included in the thin slice

- **prophet-control-plane**
  - The core service that controls the local runtime, responsible for orchestration.

- **prophet-query-gateway**
  - Handles model query requests, delegating to the appropriate models.

- **prophet-trainer**
  - Responsible for running the model training process, including metrics recording.

These services will be integrated into a minimal local bootstrap environment to prove local development workflows.

## Service orchestration

The local orchestration for these services will be defined in `docker-compose.yml` for Compose-first, and `kind` or `k3d` for Kubernetes deployment at scale.

## Service lifecycle

- **up**: Start services locally
- **train**: Train a model with a specified configuration
- **register**: Register the model into the system
- **promote**: Promote the model to a production environment
- **infer**: Run inference on the trained model
- **destroy**: Tear down the local services and environment

## Next steps

1. Integration with `prophet-cli` for local command delegation
2. Enable CI integration for full test coverage of local dev lifecycle
3. Expand thin-slice services to include additional models and tools
