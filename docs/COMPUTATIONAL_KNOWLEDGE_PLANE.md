# Prophet Computational Knowledge Plane

This document captures the first implementation contract for absorbing the useful Collective Knowledge pattern into Prophet Platform without taking CK as a hard runtime dependency.

## Intent

The platform should treat computational knowledge as executable, governed, and searchable assets. A useful artifact is not just a file or repo. It is a versioned object with metadata, declared actions, inputs, outputs, runtime requirements, validation, benchmark evidence, lineage, and promotion policy.

The target acceleration loop is:

1. declare artifact metadata;
2. detect host and runtime requirements;
3. fetch or prepare bounded inputs;
4. run the workflow;
5. validate outputs;
6. benchmark speed, accuracy, energy, cost, and reproducibility where applicable;
7. emit receipts, logs, checksums, SBOMs, and lineage;
8. register the result in Sociosphere;
9. index the artifact and evidence in Sherlock/Holmes;
10. expose progress and scoreboards through Delivery Excellence.

## Why this belongs in Prophet Platform

Prophet Platform is the runtime and deployment hub. Ontogenesis should own the normative schemas and SHACL gates. Lattice Forge should own reproducible runtimes and package channels. Sociosphere should own registry and mesh health. Sherlock/Holmes should own evidence search and knowledge discovery. SourceOS should own host and image-build detection. Delivery Excellence should own scoreboards and execution metrics.

Prophet Platform binds those responsibilities into a runnable loop.

## Artifact classes

Initial artifact kinds:

- `workflow`: executable multi-step research or platform process;
- `dataset`: bounded data source with provenance, license, checksums, and preparation actions;
- `model`: model artifact or model adapter with evaluation evidence;
- `benchmark`: reproducible benchmark definition and metric contract;
- `notebook`: notebook-derived workflow after stripping interactive-only state;
- `runtime`: container, kernel, package set, or image build environment;
- `paper`: research artifact with reproduced claims and evidence;
- `agent-skill`: bounded agent action pack with policy and validation gates;
- `scoreboard`: published metric view over benchmark or delivery runs.

## Standard action verbs

All computational artifacts should converge on the following action vocabulary:

- `detect`: identify host, runtime, hardware, dependency, or capability state;
- `fetch`: retrieve external or internal source material with receipts;
- `prepare`: normalize, clean, transform, or stage inputs;
- `build`: compile, package, containerize, or materialize runtime state;
- `run`: execute the declared workflow;
- `validate`: check schema, invariants, output shape, and domain constraints;
- `benchmark`: measure performance, quality, resource use, and reproducibility;
- `tune`: perform bounded parameter or hyperparameter search;
- `publish`: publish outputs, manifests, tiles, scoreboards, or packages;
- `attest`: emit signatures, checksums, SBOMs, logs, and lineage receipts.

These verbs are intentionally stable so that agents, CLI tools, APIs, CI, notebooks, and SourceOS image builds can use one shared control surface.

## Required control contract

A `prophet-artifact.yaml` file should define:

- identity: `apiVersion`, `kind`, `metadata.name`, `metadata.version`;
- ownership: canonical repo, maintainers, and domain owner;
- artifact kind: workflow, dataset, model, benchmark, notebook, runtime, paper, agent-skill, or scoreboard;
- actions: ordered action definitions with commands or adapters;
- inputs and outputs: declared paths, URIs, schemas, checksums, and content types;
- runtime: substrate, dependencies, hardware requirements, and environment variables;
- provenance: source URI, license, attribution, receipts, and source freshness;
- policy: safety class, promotion gate, network posture, and admission constraints;
- evidence: required logs, SBOMs, checksums, signatures, and lineage objects;
- metrics: names, units, thresholds, and scoreboard publication settings.

## First vertical slice: GAIA bounded OSM ingest

The first implementation target is GAIA bounded OSM ingest because it gives us a low-risk, high-signal demonstration path:

OSM region source -> artifact manifest -> fetch/prepare/validate -> bounded ingest -> tile/API output -> provenance receipts -> Sociosphere registry entry -> Sherlock evidence index -> Delivery Excellence scoreboard -> `/map` workbench surface.

This slice exercises the core estate without granting privileged host mutation or dangerous runtime admission.

## Repository ownership map

- `SocioProphet/ontogenesis`: normative artifact ontology, JSON Schema, SHACL, Avro/JSON-LD, TriTRPC IDL generation hooks.
- `SocioProphet/prophet-platform`: artifact runner, API binding, local fixture execution, evidence emission, registry bridge.
- `SocioProphet/gaia-world-model`: GAIA artifact packs, especially bounded OSM, EO, terrain, weather, and fusion workflows.
- `SocioProphet/lattice-forge`: reproducible runtime profiles, package channels, kernels, container images, SBOM release hooks.
- `SocioProphet/sociosphere`: artifact registry, mesh health, stale/drifted artifact status, slash-topic governance surface.
- `SocioProphet/sherlock-search`: artifact/evidence indexing, retrieval, ranking, and discovery surfaces.
- `SocioProphet/holmes`: language, NLP, entity/relation, semantic, and knowledge-graph interpretation over artifacts.
- `SocioProphet/delivery-excellence`: metric model, scoreboards, run history, and delivery performance views.
- `SourceOS-Linux/sourceos-boot` and related SourceOS repos: host/image detection, boot evidence, immutable build receipts.

## Governance boundaries

Artifacts must not silently mutate hosts, secrets, live infrastructure, or privileged runtime state. Every privileged or effects-linked artifact needs explicit policy classification and promotion gates. Initial classes:

- `advisory`: documentation, analysis, or read-only evidence generation;
- `bounded`: fixture-backed or region-bounded workflow with reversible outputs;
- `privileged`: host, cluster, identity, deployment, or runtime-admission mutation;
- `prohibited`: unsafe, illegal, destructive, or ungoverned actions.

## Definition of done for v0

A minimal credible v0 is done when one declared artifact can be executed through a platform runner and produces:

- validated output;
- structured run record;
- logs and checksums;
- provenance receipts;
- policy classification;
- basic metrics;
- Sociosphere registration payload;
- Sherlock index payload;
- Delivery Excellence scoreboard payload.

## Near-term implementation sequence

1. Land the artifact schema and GAIA example contract.
2. Add a fixture-backed runner that can parse `prophet-artifact.yaml` and execute declared no-op or local-safe actions.
3. Emit a stable run-record JSON object.
4. Add validation for required actions, metadata, provenance, policy, and evidence fields.
5. Add a GAIA bounded OSM fixture pack with attribution/provenance placeholders.
6. Add Sociosphere registry export.
7. Add Sherlock/Holmes indexing export.
8. Add Delivery Excellence metric export.
9. Add Lattice Forge runtime profile binding.
10. Promote notebook-derived workflows through the same artifact contract.
