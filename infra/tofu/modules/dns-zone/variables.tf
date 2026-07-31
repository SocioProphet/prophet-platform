variable "domain" {
  type        = string
  description = "Apex domain for this zone, e.g. socioprophet.ai (no trailing dot)."
}

variable "role" {
  type        = string
  description = "Portfolio role: canonical | redirect | reserved | mail."
  validation {
    condition     = contains(["canonical", "redirect", "reserved", "mail"], var.role)
    error_message = "role must be one of: canonical, redirect, reserved, mail."
  }
}

variable "mail" {
  type        = bool
  default     = false
  description = <<-DESC
    Whether this domain sends email. SAFETY: when false (parked/non-mail), the module
    applies a hard anti-spoof lockdown (SPF -all, null-MX, DMARC p=reject). When true, it
    NEVER guesses live mail records: SPF/MX are left unmanaged unless explicitly provided,
    and DMARC defaults to observe mode (p=none) so deliverability cannot be broken.
  DESC
}

variable "dnssec" {
  type        = bool
  default     = true
  description = "Enable DNSSEC on the managed zone."
}

variable "dmarc_rua" {
  type        = string
  description = "Mailbox that receives DMARC aggregate/forensic reports and CAA iodef notices."
}

variable "dmarc_policy" {
  type        = string
  default     = ""
  description = "Override DMARC policy (none|quarantine|reject). Empty = derive from role: reject when mail=false, none when mail=true."
}

variable "spf" {
  type        = string
  default     = ""
  description = "Override SPF value. Empty = derive: 'v=spf1 -all' when mail=false; unmanaged when mail=true."
}

variable "mx_records" {
  type        = list(string)
  default     = []
  description = "MX rrdatas (e.g. ['1 aspmx.l.google.com.']). Empty = null-MX when mail=false; unmanaged when mail=true."
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
  description = "Additional records. name '@' = apex; otherwise a subdomain label (module appends the zone dns_name)."
}

variable "labels" {
  type        = map(string)
  default     = {}
  description = "Extra labels merged onto the managed zone."
}
