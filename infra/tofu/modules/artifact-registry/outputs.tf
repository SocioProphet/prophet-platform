output "repository_urls" {
  description = "Map of repo slug → full Docker registry URL"
  value = {
    for k, v in google_artifact_registry_repository.repos :
    k => "${var.location}-docker.pkg.dev/${var.project_id}/${k}"
  }
}
