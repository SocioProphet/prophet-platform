# GCP state bootstrap — run ONCE before any other GCP tofu envs.
# Creates the GCS bucket that backs all gcp-* backend blocks.
# Uses a local backend here; migrate to GCS after first apply if desired.
# Never destroy without migrating state first.

terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
  # Intentional: this bootstrap itself uses a local state file.
  # Once applied, all OTHER envs use the GCS bucket we create here.
}

provider "google" {
  project = var.project_id
}

resource "google_storage_bucket" "tofu_state" {
  name                        = var.state_bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning { enabled = true }

  lifecycle_rule {
    condition { num_newer_versions = 10 }
    action { type = "Delete" }
  }

  labels = local.labels

  lifecycle { prevent_destroy = true }
}

resource "google_storage_bucket_iam_member" "platform_admins" {
  bucket = google_storage_bucket.tofu_state.name
  role   = "roles/storage.objectAdmin"
  member = "group:${var.admin_group_email}"
}

locals {
  labels = {
    managed-by  = "opentofu"
    environment = "bootstrap"
    team        = "platform"
    repo        = "socioprophet-prophet-platform"
  }
}

output "state_bucket_name" {
  value       = google_storage_bucket.tofu_state.name
  description = "Use this as bucket = \"...\" in all gcp-* backend blocks."
}
output "state_bucket_url" {
  value = "gs://${google_storage_bucket.tofu_state.name}"
}
