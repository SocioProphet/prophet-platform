# infra/tofu/shared/ is NOT a shared include. OpenTofu has no include mechanism
# for root modules — a `terraform { required_providers }` block is only read from
# the root directory `tofu init` is run in. This directory is a sibling root that
# declares no backend and no resources; the envs reference ../../modules/*, never
# this path. Nothing here reaches any env.
#
# This file used to pin google/google-beta at ~> 6.0 with the comment "used only
# in envs/gcp-* and modules that explicitly declare provider". That was false in
# both directions: no env loaded this file, and no env pinned anything, so
# envs/{gcp-landing,shared,prod} resolved google 7.42.0 — one major above the
# intent stated right here. The pins now live where they are actually read:
#
#   infra/tofu/envs/local/versions.tf
#   infra/tofu/envs/gcp-landing/versions.tf
#   infra/tofu/envs/shared/versions.tf
#   infra/tofu/envs/prod/versions.tf
#   infra/tofu/environments/*/versions.tf   (already pinned)
#   infra/tofu/bootstrap/*/main.tf          (already pinned)
#
# No required_providers block below: labels.tf is a locals-only fragment and this
# root uses no provider. Declaring providers here installed and locked six of them
# for a configuration with zero resources — a required_providers entry is fetched
# even when nothing references it.
#
# If this directory ever gains resources, add the providers it actually uses.
# Do not restore an estate-wide pin list here; it cannot constrain anything else.

terraform {
  required_version = ">= 1.8.0"
}
