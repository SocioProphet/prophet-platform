resource "google_artifact_registry_repository" "repos" {
  for_each = var.repositories

  project       = var.project_id
  location      = var.location
  repository_id = each.key
  description   = each.value.description
  format        = each.value.format

  docker_config {
    immutable_tags = each.value.immutable_tags
  }

  labels = {
    "managed-by"       = "opentofu"
    "prophet-platform" = "true"
    "surface"          = each.key
  }
}

# Grant reader access for deploy SAs
resource "google_artifact_registry_repository_iam_member" "readers" {
  for_each = {
    for pair in setproduct(keys(var.repositories), var.reader_service_accounts) :
    "${pair[0]}/${pair[1]}" => { repo = pair[0], sa = pair[1] }
  }

  project    = var.project_id
  location   = var.location
  repository = each.value.repo
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${each.value.sa}"

  depends_on = [google_artifact_registry_repository.repos]
}
