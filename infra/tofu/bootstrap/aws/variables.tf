variable "region" {
  type    = string
  default = "us-east-1"
}
variable "state_bucket_name" {
  type    = string
  default = "prophet-tofu-state-aws"
}
variable "lock_table_name" {
  type    = string
  default = "prophet-tofu-locks-aws"
}
