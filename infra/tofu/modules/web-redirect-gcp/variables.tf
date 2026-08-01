variable "project" {
  type        = string
  description = "GCP project for the redirect load balancer."
}

variable "name_prefix" {
  type        = string
  default     = "dns-redirect"
  description = "Name prefix for the LB resources."
}

variable "redirects" {
  type        = map(string)
  description = "Map of redirect host -> canonical target host (301). e.g. { \"socioprophet.org\" = \"socioprophet.com\" }."
}

variable "default_target" {
  type        = string
  description = "Fallback 301 target for requests that match no host rule."
}

variable "cert_domains" {
  type        = list(string)
  description = "Domains the Google-managed SSL cert must cover (apex + www of each redirect host)."
}
