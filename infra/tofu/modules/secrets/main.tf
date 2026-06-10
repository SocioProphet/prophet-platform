# Secret Manager — no SA keys, no secrets in git (ADR-050)
variable "project_id" {
  type = string
}

variable "secrets" {
  type = map(object({
    # initial_value: set once at creation; rotated out-of-band.
    # Leave empty to create the secret shell without a version (populate separately).
    initial_value = optional(string, "")
    replication   = optional(string, "automatic") # automatic | user-managed
    accessor_sas  = optional(list(string), [])
  }))
  description = "Map of secret slug → config."
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = var.secrets
  project   = var.project_id
  secret_id = each.key

  replication {
    dynamic "auto" {
      for_each = each.value.replication == "automatic" ? [1] : []
      content {}
    }
    dynamic "user_managed" {
      for_each = each.value.replication != "automatic" ? [1] : []
      content {
        replicas {
          location = "us-central1"
        }
      }
    }
  }

  labels = { "managed-by" = "opentofu", "prophet-platform" = "true" }
}

resource "google_secret_manager_secret_version" "initial" {
  for_each    = { for k, v in var.secrets : k => v if v.initial_value != "" }
  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value.initial_value

  lifecycle {
    # Never replace a secret version via tofu — rotate externally
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_iam_member" "accessors" {
  for_each = {
    for pair in flatten([
      for slug, cfg in var.secrets : [
        for sa in cfg.accessor_sas : { key = "${slug}/${sa}", slug = slug, sa = sa }
      ]
    ]) : pair.key => pair
  }

  project   = var.project_id
  secret_id = google_secret_manager_secret.secrets[each.value.slug].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value.sa}"
}

output "secret_ids" {
  value = { for k, v in google_secret_manager_secret.secrets : k => v.id }
}
