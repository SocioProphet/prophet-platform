# GKE Autopilot cluster + Artifact Registry for the prophet-platform Lane C
# runtime. Autopilot = Google-managed nodes (least ops); Workload Identity is on
# by default so workloads auth to GCP without keys.
#
# Labels come from ../../shared/labels.tf conventions (inlined here to keep the
# env self-contained for `tofu apply` from this directory).

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  labels = {
    "prophet-platform" = "true"
    "managed-by"       = "opentofu"
    "source-of-truth"  = "git"
    "org"              = "socioprophet"
  }
}

# Required APIs.
resource "google_project_service" "svc" {
  for_each = toset([
    "container.googleapis.com",
    "artifactregistry.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# Container registry the build-image workflow pushes to.
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "socioprophet"
  format        = "DOCKER"
  description   = "SocioProphet/SourceOS estate container images"
  labels        = local.labels
  depends_on    = [google_project_service.svc]
}

# Autopilot cluster.
resource "google_container_cluster" "this" {
  name                = var.cluster_name
  location            = var.region
  enable_autopilot    = true
  deletion_protection = true

  # Autopilot manages node pools; Workload Identity is enabled implicitly.
  release_channel { channel = "REGULAR" }

  resource_labels = local.labels
  depends_on      = [google_project_service.svc]
}

# Cluster auth for the kubernetes/helm providers.
data "google_client_config" "default" {}
