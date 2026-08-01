# Provider pins for the `envs/shared` root.
#
# OpenTofu has no include mechanism for root modules: `required_providers` is
# only read from the root it lives in. Every root under infra/tofu/ therefore
# carries its own versions.tf. infra/tofu/shared/ is NOT included by anything —
# see the note in infra/tofu/shared/versions.tf. (That directory and this env
# share a name and nothing else.)
#
# google is held at 6.x to match environments/gcp-* (gcp-gke, gcp-ephemeral,
# gcp-persistent). Before this file existed the root was unconstrained and
# resolved whatever was newest that day — 7.42.0 as of 2026-07-29, a full major
# above the intent recorded in shared/versions.tf.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google      = { source = "hashicorp/google", version = "~> 6.0" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 6.0" }
  }
}
