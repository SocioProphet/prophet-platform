resource "google_project" "projects" {
  for_each = var.projects

  project_id      = each.value.project_id
  name            = each.value.display_name
  org_id          = var.org_id
  billing_account = var.billing_account
  folder_id       = each.value.folder_ids[each.value.folder_key]

  labels = merge(
    { "managed-by" = "opentofu", "prophet-platform" = "true" },
    each.value.labels
  )

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_project_service" "services" {
  for_each = {
    for pair in flatten([
      for proj_key, proj in var.projects : [
        for svc in proj.services : { key = "${proj_key}/${svc}", project = proj.project_id, service = svc }
      ]
    ]) : pair.key => pair
  }

  project                    = google_project.projects[split("/", each.key)[0]].project_id
  service                    = each.value.service
  disable_dependent_services = false
  disable_on_destroy         = false
}
