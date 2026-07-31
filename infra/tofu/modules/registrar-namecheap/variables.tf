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
