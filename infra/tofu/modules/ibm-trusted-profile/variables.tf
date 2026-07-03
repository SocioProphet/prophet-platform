variable "profile_name_suffix" {
  type    = string
  default = "prophet-platform"
}
variable "github_repo" {
  type        = string
  description = "GitHub repo in owner/name format (e.g. SocioProphet/prophet-platform)"
}
variable "cluster_id" {
  type        = string
  description = "IBM IKS cluster resource instance ID"
}
variable "cos_instance_crn" {
  type        = string
  description = "CRN of the IBM COS instance holding the Tofu state bucket"
}
variable "state_bucket_name" {
  type        = string
  default     = "prophet-tofu-state-ibm"
}
