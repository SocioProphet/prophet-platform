variable "org_domain" {
  type        = string
  description = "GCP org domain (e.g. socioprophet.ai)"
}

variable "billing_account" {
  type        = string
  description = "GCP billing account ID"
}

variable "admin_group_email" {
  type        = string
  description = "Google Group that receives org-admin IAM binding"
}
