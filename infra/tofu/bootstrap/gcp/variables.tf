variable "project_id" {
  type        = string
  description = "GCP project that will own the state bucket (typically the platform project)."
}
variable "state_bucket_name" {
  type    = string
  default = "prophet-tofu-state-prod"
}
variable "location" {
  type    = string
  default = "US"
}
variable "admin_group_email" {
  type    = string
  default = "platform-admins@socioprophet.ai"
}
