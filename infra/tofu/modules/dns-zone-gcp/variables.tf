variable "zone_name" {
  type        = string
  description = "RFC1035 managed zone name."
}

variable "dns_name" {
  type        = string
  description = "Zone dns_name with trailing dot."
}

variable "dnssec" {
  type        = bool
  default     = true
  description = "Sign the zone with DNSSEC."
}

variable "role" {
  type        = string
  description = "Portfolio role, used for labeling/description only."
}

variable "records" {
  type = list(object({
    name    = string
    type    = string
    ttl     = number
    rrdatas = list(string)
  }))
  description = "Normalized records from the dns-records module."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Extra zone labels."
}
