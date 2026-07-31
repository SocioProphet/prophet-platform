variable "domain" {
  type        = string
  description = "The registrable domain whose nameservers are delegated (no trailing dot), for example socioprophet.ai"
}

variable "name_servers" {
  type        = list(string)
  description = "Nameservers to set at the registrar (from the Cloud DNS zone output)."
}

variable "enabled" {
  type        = bool
  default     = false
  description = "Guard: only touch the registrar when true. Setting NS is a hard-to-reverse, prod-affecting change; keep false until a plan is reviewed and the Namecheap API client_ip is allowlisted."
}

variable "role" {
  type        = string
  default     = "reserved"
  description = "Portfolio role of the domain, used by the fail-closed delegation guard."
}

variable "has_records" {
  type        = bool
  default     = false
  description = "Whether the domain has any non-baseline records. Delegating a canonical/redirect domain with none would make it resolve to nothing."
}
