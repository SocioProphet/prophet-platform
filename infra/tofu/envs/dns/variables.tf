variable "dns_cloud" {
  type        = string
  default     = "gcp"
  description = "Which cloud emitter renders the records: gcp | aws. Adding a cloud = a new emitter module against the dns-records contract."
  validation {
    condition     = contains(["gcp", "aws"], var.dns_cloud)
    error_message = "dns_cloud must be one of: gcp, aws."
  }
}

variable "project" {
  type        = string
  default     = ""
  description = "GCP project hosting the Cloud DNS zones (required when dns_cloud=gcp)."
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for the provider (Route53 is global; region is for the provider handshake)."
}

variable "dmarc_rua" {
  type        = string
  default     = "dmarc@socioprophet.ai"
  description = "Mailbox for DMARC reports and CAA iodef across the portfolio. Its domain hosts the cross-domain _report._dmarc authorizations."
}

variable "manage_registrar" {
  type        = bool
  default     = false
  description = "When true, delegate NS at Namecheap for domains with manage_ns:true. Keep false until a plan is reviewed and the API client_ip is allowlisted."
}

variable "enable_redirects" {
  type        = bool
  default     = false
  description = "When true (and dns_cloud=gcp), stand up the redirect LB and point redirect-role domains' apex/www A records at it. Off by default (creates a global IP + managed cert)."
}

variable "default_redirect_target" {
  type        = string
  default     = "socioprophet.com"
  description = "Canonical 301 target for redirect-role domains that don't set redirect_to."
}

variable "create_egress_nat" {
  type        = bool
  default     = false
  description = "Provision a reserved static egress IP + Cloud NAT so the registrar API can be called from an allowlistable fixed IP. Requires egress_network."
}

variable "egress_network" {
  type        = string
  default     = ""
  description = "VPC network (name or self_link) for the egress NAT. Required when create_egress_nat=true."
}

variable "egress_region" {
  type        = string
  default     = "us-central1"
  description = "Region for the egress NAT."
}

variable "namecheap_user_name" {
  type        = string
  default     = ""
  description = "Namecheap account username."
}

variable "namecheap_api_user" {
  type        = string
  default     = ""
  description = "Namecheap API user."
}

variable "namecheap_api_key" {
  type        = string
  default     = ""
  sensitive   = true
  description = "Namecheap API key. Mint in CI; never commit."
}

variable "namecheap_client_ip" {
  type        = string
  default     = ""
  description = "Public IP calling the Namecheap API. MUST be allowlisted (use the egress-nat static IP)."
}

variable "namecheap_sandbox" {
  type        = bool
  default     = false
  description = "Use the Namecheap sandbox API."
}
