# One Cloud DNS managed zone per domain, with a safety-aware email-security baseline.
# Parked/non-mail domains are locked down hard (they are spoofable otherwise); mail
# domains are never auto-guessed (see variable "mail").

locals {
  zone_id  = replace(var.domain, ".", "-")
  dns_name = "${var.domain}."

  # SPF: hard reject for parked; unmanaged for mail unless explicitly provided.
  spf_value  = var.spf != "" ? var.spf : (var.mail ? "" : "v=spf1 -all")
  manage_spf = local.spf_value != ""

  # Cloud DNS keeps ALL TXT strings for a name in ONE record set. Fold SPF together with
  # any apex TXT supplied via app_records (e.g. a domain-verification token) so they don't
  # collide as two record sets at the apex.
  apex_txt_extra   = flatten([for r in var.app_records : r.rrdatas if r.name == "@" && upper(r.type) == "TXT"])
  spf_rrdata       = local.manage_spf ? ["\"${local.spf_value}\""] : []
  apex_txt_all     = concat(local.spf_rrdata, local.apex_txt_extra)
  manage_apex_txt  = length(local.apex_txt_all) > 0
  app_records_rest = [for r in var.app_records : r if !(r.name == "@" && upper(r.type) == "TXT")]

  # MX: null-MX (RFC 7505) for parked; unmanaged for mail unless explicitly provided.
  mx_rrdatas = length(var.mx_records) > 0 ? var.mx_records : (var.mail ? [] : ["0 ."])
  manage_mx  = length(local.mx_rrdatas) > 0

  # DMARC: reject for parked; observe (none) for mail unless overridden.
  dmarc_policy = var.dmarc_policy != "" ? var.dmarc_policy : (var.mail ? "none" : "reject")
  dmarc_value  = "v=DMARC1; p=${local.dmarc_policy}; rua=mailto:${var.dmarc_rua}; ruf=mailto:${var.dmarc_rua}; fo=1; adkim=s; aspf=s"

  caa_rrdatas = concat(
    [for ca in var.caa_issuers : "0 issue \"${ca}\""],
    ["0 iodef \"mailto:${var.dmarc_rua}\""],
  )
}

resource "google_dns_managed_zone" "this" {
  name        = local.zone_id
  dns_name    = local.dns_name
  description = "Managed by tofu envs/dns — role=${var.role}"
  labels = merge({
    role       = var.role
    managed_by = "tofu-dns-portfolio"
  }, var.labels)

  dynamic "dnssec_config" {
    for_each = var.dnssec ? [1] : []
    content {
      state = "on"
    }
  }
}

resource "google_dns_record_set" "apex_txt" {
  count        = local.manage_apex_txt ? 1 : 0
  name         = local.dns_name
  type         = "TXT"
  ttl          = 3600
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = local.apex_txt_all
}

resource "google_dns_record_set" "mx" {
  count        = local.manage_mx ? 1 : 0
  name         = local.dns_name
  type         = "MX"
  ttl          = 3600
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = local.mx_rrdatas
}

resource "google_dns_record_set" "dmarc" {
  name         = "_dmarc.${local.dns_name}"
  type         = "TXT"
  ttl          = 3600
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = ["\"${local.dmarc_value}\""]
}

resource "google_dns_record_set" "caa" {
  name         = local.dns_name
  type         = "CAA"
  ttl          = 3600
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = local.caa_rrdatas
}

resource "google_dns_record_set" "app" {
  for_each     = { for r in local.app_records_rest : "${r.type}:${r.name}" => r }
  name         = each.value.name == "@" ? local.dns_name : "${each.value.name}.${local.dns_name}"
  type         = each.value.type
  ttl          = each.value.ttl
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = each.value.rrdatas
}
