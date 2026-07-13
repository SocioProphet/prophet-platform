output "cluster_name" {
  value = google_container_cluster.this.name
}

output "cluster_endpoint" {
  value     = google_container_cluster.this.endpoint
  sensitive = true
}

output "get_credentials" {
  description = "Run this to point kubectl at the cluster (needs gke-gcloud-auth-plugin + a fresh `gcloud auth login`)."
  value       = "gcloud container clusters get-credentials ${google_container_cluster.this.name} --region ${var.region} --project ${var.project_id}"
}
