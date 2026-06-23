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

# Let the CI service account (the build-image push identity) write images.
resource "google_artifact_registry_repository_iam_member" "ci_push" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:sourceos-ci@socioprophet-platform.iam.gserviceaccount.com"
}

# Dedicated, least-privilege node identity. The project's default compute SA was
# deleted (hardening), so Autopilot can't fall back to it — and a custom node SA
# is best practice regardless.
resource "google_service_account" "gke_nodes" {
  account_id   = "gke-prophet-nodes"
  display_name = "GKE prophet-platform node identity"
}

resource "google_project_iam_member" "gke_nodes" {
  for_each = toset([
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/monitoring.viewer",
    "roles/stackdriver.resourceMetadata.writer",
    "roles/artifactregistry.reader", # pull images from GAR
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

# Autopilot cluster.
resource "google_container_cluster" "this" {
  name                = var.cluster_name
  location            = var.region
  enable_autopilot    = true
  deletion_protection = false

  # Autopilot manages node pools; Workload Identity is enabled implicitly.
  release_channel { channel = "REGULAR" }

  # Autopilot node identity (replaces the deleted default compute SA).
  cluster_autoscaling {
    auto_provisioning_defaults {
      service_account = google_service_account.gke_nodes.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  resource_labels = local.labels
  depends_on      = [google_project_service.svc, google_project_iam_member.gke_nodes]
}

# Cluster auth for the kubernetes/helm providers.
data "google_client_config" "default" {}
