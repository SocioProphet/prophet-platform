# Ephemeral stack — the CATTLE. GKE Autopilot cluster + Argo CD. `tofu apply` to
# spin up, `tofu destroy` to tear down. Destroying this leaves the persistent stack
# (registry, buckets, retained disks, node SA) completely untouched, so images +
# data survive; the next spin-up re-binds the disks and Argo re-syncs the stack.
#
# Backend: LOCAL state (ephemeral — nothing here is precious; destroy removes it).
# Auth: Application-Default Credentials.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google     = { source = "hashicorp/google", version = "~> 6.0" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
