# Delegates a Namecheap domain's nameservers to Cloud DNS. Registrar-only: this module
# never manages host records (those live in Cloud DNS). Custom nameservers and host
# records are mutually exclusive at Namecheap, so setting NS here hands DNS to Cloud DNS.

resource "namecheap_domain_records" "delegation" {
  count       = var.enabled ? 1 : 0
  domain      = var.domain
  mode        = "OVERWRITE"
  nameservers = var.name_servers

  lifecycle {
    precondition {
      # Fail closed: refuse to delegate a canonical/redirect domain that has no records —
      # delegation replaces the registrar's DNS entirely, so it would resolve to nothing.
      condition     = !(contains(["canonical", "redirect"], var.role) && !var.has_records)
      error_message = "Refusing to delegate ${var.domain}: role=${var.role} has no non-baseline records; delegation would make it resolve to nothing. Add records in domains.yaml (or a redirect target) first."
    }
  }
}
