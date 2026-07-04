variable "subscription_id" { type = string }
variable "location" {
  type    = string
  default = "eastus"
}
variable "storage_account_name" {
  type        = string
  default     = "prophettofustate"
  description = "Must be globally unique, 3-24 chars, lowercase alphanumeric."
}
