# Persistent stack — the durable foundation that OUTLIVES every cluster teardown:
# Artifact Registry (images), GCS buckets (blobs/backups), and retained Persistent
# Disks (hellgraph estate RocksDB + self-hosted Postgres data). Apply once; you
# almost never destroy this. `tofu destroy` on the EPHEMERAL stack leaves all of
# this untouched, so images + data survive across spin-ups.
#
# Backend: LOCAL state (this env changes rarely). Back up `terraform.tfstate` —
# it's the map to the durable resources. Auth: Application-Default Credentials
# (gcloud auth application-default login), NOT the gcloud CLI session.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
