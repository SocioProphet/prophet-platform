# Provider pins for the `envs/local` root.
#
# OpenTofu has no include mechanism for root modules: `required_providers` is
# only read from the root it lives in. Every root under infra/tofu/ therefore
# carries its own versions.tf. infra/tofu/shared/ is NOT included by anything —
# see the note in infra/tofu/shared/versions.tf.
#
# This env is deliberately cloud-free (k3d only). Do not add google/aws/azurerm
# here: a required_providers entry is installed and locked even when no resource
# uses it, so listing a cloud provider would make the local dev loop depend on it.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    local  = { source = "hashicorp/local", version = "~> 2.5" }
    null   = { source = "hashicorp/null", version = "~> 3.2" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
