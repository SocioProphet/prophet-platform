variable "project" {
  type        = string
  description = "GCP project that hosts the Cloud DNS managed zones."
}

variable "dmarc_rua" {
  type        = string
  default     = "dmarc@socioprophet.ai"
  description = "Mailbox for DMARC reports and CAA iodef notices across the portfolio."
}

variable "manage_registrar" {
  type        = bool
  default     = false
  description = "When true, delegate NS at Namecheap for domains with manage_ns:true. Keep false until a plan is reviewed and the API client_ip is allowlisted."
}

variable "create_egress_nat" {
  type        = bool
  default     = false
  description = "When true, provision a reserved static egress IP + Cloud NAT (module egress-nat) so the registrar API can be called from an allowlistable fixed IP. Requires egress_network."
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
  description = "The public IP calling the Namecheap API. MUST be allowlisted in the Namecheap API settings (use a static egress IP / bastion — CI runner IPs are dynamic)."
}

variable "namecheap_sandbox" {
  type        = bool
  default     = false
  description = "Use the Namecheap sandbox API."
}
