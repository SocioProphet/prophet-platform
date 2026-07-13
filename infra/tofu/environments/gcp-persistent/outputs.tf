# Consumed by the EPHEMERAL stack (via data sources) and the workload charts
# (static PVs bind the disks by self-link; services read the bucket names).

output "registry" {
  description = "Docker registry path for image pushes/pulls."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "blobs_bucket" {
  value = google_storage_bucket.blobs.name
}

output "backups_bucket" {
  value = google_storage_bucket.backups.name
}

output "hellgraph_disk" {
  description = "Self-link of the retained hellgraph estate disk (for the static PV volumeHandle)."
  value       = google_compute_disk.hellgraph_estate.self_link
}

output "hellgraph_disk_name" {
  value = google_compute_disk.hellgraph_estate.name
}

output "postgres_disk" {
  value = google_compute_disk.postgres_data.self_link
}

output "postgres_disk_name" {
  value = google_compute_disk.postgres_data.name
}

output "zone" {
  value = var.zone
}

output "gke_node_sa" {
  description = "Email of the long-lived GKE node identity (consumed by the ephemeral cluster stack)."
  value       = google_service_account.gke_nodes.email
}
