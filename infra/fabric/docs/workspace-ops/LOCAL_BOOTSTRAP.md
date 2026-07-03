# Local Bootstrap — Workspace Ops Prototype and Mesh

## Current failure pattern

If this command fails:

```bash
make validate-workspace-all
```

with:

```text
make: *** No rule to make target `validate-workspace-all'.  Stop.
```

then the local checkout does not contain the current root `Makefile`, or the command is being run outside the repository root.

## Bring local checkout current

From the local repository path:

```bash
cd ~/dev/prophet-platform-fabric-mlops-ts-suite
git status --short
git branch --show-current
git remote -v
git fetch --all --prune
git pull --ff-only
ls -la Makefile
make help
```

If `git pull --ff-only` fails because of local changes, inspect them with:

```bash
git status
git diff
```

Do not force reset until local changes are understood.

## Local check

After pulling:

```bash
make doctor-workspace-ops
```

or directly:

```bash
python3 scripts/check_workspace_ops.py
```

## Install OpenTofu on macOS

OpenTofu is the preferred IaC binary for this mesh. With Homebrew installed:

```bash
brew update
brew install opentofu
tofu -version
```

If Homebrew is not installed, install OpenTofu using one of the official non-Homebrew methods from the OpenTofu documentation.

## Validate and plan mesh

After OpenTofu is available:

```bash
make validate-workspace-all
make terraform-workspace-mesh-init
make terraform-workspace-mesh-validate
make terraform-workspace-mesh-plan
```

The target names retain `terraform-*` for operator familiarity but run `tofu` by default through `IAC ?= tofu`.

## Terraform compatibility override

Terraform can be used explicitly if required:

```bash
make IAC=terraform terraform-workspace-mesh-plan
```

OpenTofu remains the preferred default for new SocioProphet mesh work.
