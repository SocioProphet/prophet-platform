variable "project_id" { type = string }
variable "github_repo" {
  type        = string
  description = "GitHub repo in owner/name format (e.g. SocioProphet/prophet-platform)"
}
variable "state_bucket_name" {
  type        = string
  description = "GCS bucket holding Tofu state — grants objectAdmin to the CI SA"
  default     = "prophet-tofu-state-prod"
}
