variable "zone_name" {
  type        = string
  description = "DNS zone (e.g. socioprophet.ai)"
}

variable "control_plane_ip" {
  type        = string
  description = "Public IP of the control-plane / LB"
}

variable "subdomain_prefix" {
  type    = string
  default = ""
  description = "Optional subdomain prefix (e.g. 'p1' → p1.socioprophet.ai). Empty = apex."
}
