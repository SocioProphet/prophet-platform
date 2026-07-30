variable "zone_name" {
  type        = string
  description = "DNS zone (e.g. socioprophet.ai)"
}

variable "control_plane_ip" {
  type        = string
  description = "Public IP of the HTTP(S) ingress / control-plane LB (caldav, storage, argocd A records)"
}

variable "subdomain_prefix" {
  type        = string
  default     = ""
  description = "Optional subdomain prefix (e.g. 'p1' → p1.socioprophet.ai). Empty = apex."
}

# --- Mail plane (Postfix/Dovecot). These records were previously a runbook of manual steps; now generated. ---

variable "smtp_ip" {
  type        = string
  default     = ""
  description = "Static IP of the SMTP LoadBalancer (ports 25/587). MX target + mail.<zone> A record. Set PTR on this IP → mail.<zone>. Empty = mail records omitted."
}

variable "imap_ip" {
  type        = string
  default     = ""
  description = "Static IP of the IMAPS LoadBalancer (port 993). imap.<zone> A record. Empty = falls back to smtp_ip."
}

variable "dkim_selector" {
  type        = string
  default     = "default"
  description = "DKIM selector; publishes <selector>._domainkey.<zone>."
}

variable "dkim_public_key" {
  type        = string
  default     = ""
  description = "DKIM public key (base64 DER, the p= value). Empty = DKIM TXT omitted."
}

variable "dmarc_policy" {
  type        = string
  default     = "none"
  description = "DMARC policy: none (monitor — safe default during rollout) | quarantine | reject."
  validation {
    condition     = contains(["none", "quarantine", "reject"], var.dmarc_policy)
    error_message = "dmarc_policy must be one of: none, quarantine, reject."
  }
}

variable "dmarc_rua" {
  type        = string
  default     = ""
  description = "DMARC aggregate-report address. Empty = postmaster@<zone>."
}

variable "spf_hardfail" {
  type        = bool
  default     = false
  description = "SPF all-qualifier: false = ~all (softfail, safe during warm-up), true = -all (hardfail, once reputation is established)."
}

variable "spf_includes" {
  type        = list(string)
  default     = []
  description = "Extra SPF include: mechanisms merged into the SINGLE SPF record — e.g. [\"_spf.google.com\"] while migrating off Google Workspace. A domain may have exactly ONE SPF record; this coexists our IP with the incumbent instead of emitting a second (invalid) record."
}
