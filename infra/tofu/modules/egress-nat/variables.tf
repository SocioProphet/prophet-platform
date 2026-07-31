variable "project" {
  type        = string
  description = "GCP project for the egress NAT."
}

variable "region" {
  type        = string
  description = "Region for the router, NAT, and reserved address."
}

variable "network" {
  type        = string
  description = "VPC network (name or self_link) the router attaches to. Whatever runs the registrar call (self-hosted runner / Cloud Run job / GCE) must egress through this network to get the fixed IP."
}

variable "name_prefix" {
  type        = string
  default     = "dns-egress"
  description = "Name prefix for the address, router, and NAT."
}

variable "num_static_ips" {
  type        = number
  default     = 1
  description = "Number of reserved external IPs to allocate for NAT egress."
}

variable "log_nat" {
  type        = bool
  default     = true
  description = "Enable Cloud NAT error logging."
}
