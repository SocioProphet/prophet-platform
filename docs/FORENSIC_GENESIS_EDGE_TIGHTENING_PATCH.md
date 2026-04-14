# Forensic Genesis Edge Tightening Patch

This note records the two remaining **surgical in-place edits** that are still desirable after the additive runtime lane landed.

They were not applied through the current connector path because the available live-write surface here is reliable for additive file creation but not for safe branch-isolated edits of existing tracked files.

## Desired `standards.lock.yaml` addition

Add a new entry under `spec.imports.normative_standards`:

```yaml
      forensic-genesis-edge:
        repo: SocioProphet/prophet-platform-standards
        class: runtime-profile
        channel: controlled
        pin:
          commit: 27be5c63098f443175a1507655ce9b7a094fc134
          tag: null
        consume:
          docs:
            - docs/FORENSIC_GENESIS_EDGE.md
          generated_artifacts:
            - contracts/forensic-genesis/
            - docs/LOCAL-FORENSIC-GENESIS-EDGE.md
            - infra/local/docker-compose.forensic-genesis-edge.yml
        rules:
          runtimeConformanceRequiredForForensicGenesisEdge: true
          standardsRepoRemainsNormative: true
```

## Desired root `Makefile` tightening

1. Extend the `.PHONY` line to include `validate-forensic-edge`.
2. Extend the `validate:` target to include `validate-forensic-edge`.
3. Add:

```make
validate-forensic-edge:
	python3 tools/validate_forensic_genesis_edge.py
	python3 tools/validate_forensic_genesis_edge_pin.py
```

## Why this still matters

The additive runtime lane is already live:
- local broker lane compose file
- runtime validator
- dedicated workflow
- standards pin artifact
- standards pin validator

But these two surgical edits would make the new edge lane part of the repo's **default** standards and validation fabric instead of remaining an additive side lane.
