variable "zone_name" {
  type        = string
  description = "Logical zone name (unused by Route53, kept for interface parity)."
  default     = ""
}

variable "dns_name" {
  type        = string
  description = "Zone dns_name with trailing dot."
}

variable "dnssec" {
  type        = bool
  default     = true
  description = "Sign the zone. NOTE: Route53 DNSSEC needs a KMS KSK (not yet implemented here); this emitter fails closed if dnssec=true."
}

variable "role" {
  type        = string
  description = "Portfolio role, used for tagging only."
}

variable "records" {
  type = list(object({
    name    = string
    type    = string
    ttl     = number
    rrdatas = list(string)
  }))
  description = "Normalized records from the dns-records module (identical shape to the GCP emitter)."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Extra tags."
}
