variable "domain" {
  type        = string
  description = "Apex domain, no trailing dot (e.g. socioprophet.ai)."
}

variable "role" {
  type        = string
  description = "Portfolio taxonomy only: canonical | redirect | reserved. Mail behavior is var.mail."
  validation {
    condition     = contains(["canonical", "redirect", "reserved"], var.role)
    error_message = "role must be one of: canonical, redirect, reserved."
  }
}

variable "mail" {
  type        = bool
  default     = false
  description = "false (default) = hard anti-spoof lockdown (SPF -all, null-MX, DMARC p=reject). true = never guess live mail (SPF/MX unmanaged, DMARC observe p=none)."
}

variable "dnssec" {
  type        = bool
  default     = true
  description = "Whether the emitter should sign the zone."
}

variable "dmarc_rua" {
  type        = string
  description = "Mailbox for DMARC reports and CAA iodef."
}

variable "dmarc_policy" {
  type        = string
  default     = ""
  description = "Override DMARC policy. Empty = derive (reject when mail=false, none when mail=true)."
  validation {
    condition     = var.dmarc_policy == "" || contains(["none", "quarantine", "reject"], var.dmarc_policy)
    error_message = "dmarc_policy must be empty or one of: none, quarantine, reject."
  }
}

variable "spf" {
  type        = string
  default     = ""
  description = "Override SPF. Empty = derive (v=spf1 -all when mail=false; unmanaged when mail=true)."
}

variable "mx_records" {
  type        = list(string)
  default     = []
  description = "MX rrdatas. Empty = null-MX when mail=false; unmanaged when mail=true."
}

variable "caa_issuers" {
  type        = list(string)
  default     = ["pki.goog", "letsencrypt.org"]
  description = "CAA authorized issuers."
}

variable "app_records" {
  type = list(object({
    name    = string
    type    = string
    ttl     = optional(number, 300)
    rrdatas = list(string)
  }))
  default     = []
  description = "Extra records. name '@' = apex. Apex TXT is folded into the single apex TXT set."
}

variable "report_authorizations" {
  type        = list(string)
  default     = []
  description = "External domains to authorize for DMARC aggregate reporting to this zone's rua mailbox (RFC 7489 §7.1). Set only on the rua domain's zone; emits <ext>._report._dmarc records."
}
