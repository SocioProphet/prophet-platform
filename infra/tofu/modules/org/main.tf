data "google_organization" "org" {
  domain = var.org_domain
}

# Org-level IAM: admin group only — no individual user bindings at org level
resource "google_organization_iam_binding" "org_admin" {
  org_id  = data.google_organization.org.org_id
  role    = "roles/resourcemanager.organizationAdmin"
  members = ["group:${var.admin_group_email}"]
}

# Deny service account key creation org-wide (ADR-050: no long-lived keys)
resource "google_org_policy_policy" "deny_sa_key_creation" {
  name   = "organizations/${data.google_organization.org.org_id}/policies/iam.disableServiceAccountKeyCreation"
  parent = "organizations/${data.google_organization.org.org_id}"

  spec {
    rules {
      enforce = true
    }
  }
}

# Require OS Login org-wide
resource "google_org_policy_policy" "require_os_login" {
  name   = "organizations/${data.google_organization.org.org_id}/policies/compute.requireOsLogin"
  parent = "organizations/${data.google_organization.org.org_id}"

  spec {
    rules {
      enforce = true
    }
  }
}
