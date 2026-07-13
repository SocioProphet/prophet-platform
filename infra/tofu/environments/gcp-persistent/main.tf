locals {
  labels = {
    "prophet-platform" = "true"
    "managed-by"       = "opentofu"
    "source-of-truth"  = "git"
    "org"              = "socioprophet"
    "lifecycle"        = "persistent"
  }
}

# Required APIs (enabled via ADC — no gcloud CLI session needed). Never disabled on
# destroy: turning an API off would ripple across the whole project.
resource "google_project_service" "svc" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "storage.googleapis.com",
    "container.googleapis.com",
    "iam.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ─── Container registry — images survive every cluster teardown ────────────────
resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "socioprophet"
  format        = "DOCKER"
  description   = "SocioProphet/SourceOS estate container images"
  labels        = local.labels
  depends_on    = [google_project_service.svc]
}

# NOTE: the CI push grant (roles/artifactregistry.writer → the build-image identity)
# is added later, when we wire the image-build pipeline — kept out of the foundation
# so this stack has zero IAM. See var.ci_service_account for the intended member.

# ─── Object storage — blobs + backups (durable) ────────────────────────────────
resource "google_storage_bucket" "blobs" {
  name                        = "prophet-blobs-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  labels                      = local.labels
  depends_on                  = [google_project_service.svc]
}

resource "google_storage_bucket" "backups" {
  name                        = "prophet-backups-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  versioning { enabled = true }
  labels     = local.labels
  depends_on = [google_project_service.svc]

  # Age off old backup versions so the bucket doesn't grow forever.
  lifecycle_rule {
    condition { age = 30 }
    action { type = "Delete" }
  }
}

# ─── Retained data disks — the point of the whole split ────────────────────────
# These zonal PDs hold hellgraph's estate RocksDB store and the self-hosted Postgres
# data. They are NOT part of the ephemeral cluster stack, so `tofu destroy` on the
# cluster leaves them intact; the next spin-up statically re-binds them (see the
# hellgraph/postgres charts' PersistentVolumes) and the data is exactly as it was.
resource "google_compute_disk" "hellgraph_estate" {
  name       = "hellgraph-estate-data"
  type       = "pd-balanced"
  zone       = var.zone
  size       = var.hellgraph_disk_gb
  labels     = local.labels
  depends_on = [google_project_service.svc]

  # Guard against an accidental `tofu destroy` wiping the estate graph.
  lifecycle { prevent_destroy = true }
}

# ─── GKE node identity — long-lived, reused by every ephemeral cluster ──────────
# MUST be persistent: a service account deleted on cluster teardown can't be
# re-created with the same account_id for 30 days (GCP soft-deletion), which would
# break the next spin-up. The project's default compute SA was deleted (hardening),
# so Autopilot needs this explicit node identity to provision nodes at all.
resource "google_service_account" "gke_nodes" {
  account_id   = "gke-prophet-nodes"
  display_name = "GKE prophet-platform node identity"
  depends_on   = [google_project_service.svc]
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

resource "google_compute_disk" "postgres_data" {
  name       = "postgres-data"
  type       = "pd-balanced"
  zone       = var.zone
  size       = var.postgres_disk_gb
  labels     = local.labels
  depends_on = [google_project_service.svc]

  lifecycle { prevent_destroy = true }
}
