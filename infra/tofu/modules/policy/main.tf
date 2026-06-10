# Org-level constraint policies — provider-agnostic design, GCP implementation
# All constraints here enforce the "no silent mutation" and provenance-first principles.

variable "org_id" {
  type = string
}
variable "folder_ids" {
  type    = map(string)
  default = {}
}

locals {
  # Constraints enforced at org level
  org_deny_constraints = [
    "constraints/iam.disableServiceAccountKeyCreation",
    "constraints/iam.disableServiceAccountKeyUpload",
    "constraints/compute.requireOsLogin",
    "constraints/compute.skipDefaultNetworkCreation",
    "constraints/compute.restrictCloudRunRegion",
  ]
}

resource "google_org_policy_policy" "org_enforced" {
  for_each = toset(local.org_deny_constraints)

  name   = "organizations/${var.org_id}/policies/${each.value}"
  parent = "organizations/${var.org_id}"

  spec {
    rules { enforce = true }
  }
}

# Restrict resource location to US (data residency)
resource "google_org_policy_policy" "restrict_locations" {
  name   = "organizations/${var.org_id}/policies/gcp.resourceLocations"
  parent = "organizations/${var.org_id}"

  spec {
    rules {
      values {
        allowed_values = ["in:us-locations"]
      }
    }
  }
}

output "applied_constraints" {
  value = keys(google_org_policy_policy.org_enforced)
}
