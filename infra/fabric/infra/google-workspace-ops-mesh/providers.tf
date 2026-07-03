provider "google" {
  project = var.google_project_id != "" ? var.google_project_id : null
}
