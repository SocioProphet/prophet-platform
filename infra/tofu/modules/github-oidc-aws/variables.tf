variable "role_name_prefix" {
  type    = string
  default = "prophet-platform"
}
variable "github_repo" {
  type        = string
  description = "GitHub repo in owner/name format (e.g. SocioProphet/prophet-platform)"
}
variable "state_bucket_name" {
  type        = string
  description = "S3 bucket holding Terraform state — grants read/write to the CI role"
}
variable "lock_table_name" {
  type        = string
  description = "DynamoDB table used for state locking"
}
variable "tags" {
  type    = map(string)
  default = {}
}
