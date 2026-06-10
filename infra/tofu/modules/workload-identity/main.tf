# Workload Identity Federation — no long-lived SA keys (ADR-050)
# GKE workloads assume GCP SAs via projected token, not key files.

resource "google_service_account" "wi_sa" {
  for_each = var.bindings

  project      = var.project_id
  account_id   = each.value.sa_name
  display_name = "${each.key} (WI)"
  description  = "Workload Identity SA for ${each.value.k8s_namespace}/${each.value.k8s_sa_name}"
}

resource "google_service_account_iam_member" "wi_binding" {
  for_each = var.bindings

  service_account_id = google_service_account.wi_sa[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${each.value.k8s_namespace}/${each.value.k8s_sa_name}]"
}

resource "google_project_iam_member" "wi_roles" {
  for_each = {
    for pair in flatten([
      for slug, cfg in var.bindings : [
        for role in cfg.roles : { key = "${slug}/${role}", slug = slug, role = role }
      ]
    ]) : pair.key => pair
  }

  project = var.project_id
  role    = each.value.role
  member  = "serviceAccount:${google_service_account.wi_sa[each.value.slug].email}"
}
