# Normalized, cloud-agnostic record model for one domain. Emits a records list that any
# per-cloud emitter can render 1:1. All safety derivation (parked lockdown vs mail observe)
# lives here, once, so it can never diverge between clouds.

locals {
  zone_name = replace(var.domain, ".", "-")
  dns_name  = "${var.domain}."

  # SPF: hard -all for parked; unmanaged for mail unless provided.
  spf_value  = var.spf != "" ? var.spf : (var.mail ? "" : "v=spf1 -all")
  manage_spf = local.spf_value != ""

  # Cloud DNS/Route53 keep ALL TXT strings for a name in ONE set; fold SPF + apex TXT.
  apex_txt_extra = flatten([for r in var.app_records : r.rrdatas if r.name == "@" && upper(r.type) == "TXT"])
  apex_txt_all   = concat(local.manage_spf ? ["\"${local.spf_value}\""] : [], local.apex_txt_extra)

  # MX: null-MX for parked; unmanaged for mail unless provided.
  mx_rrdatas = length(var.mx_records) > 0 ? var.mx_records : (var.mail ? [] : ["0 ."])

  # DMARC: reject for parked; observe for mail unless overridden.
  dmarc_policy = var.dmarc_policy != "" ? var.dmarc_policy : (var.mail ? "none" : "reject")
  dmarc_value  = "v=DMARC1; p=${local.dmarc_policy}; rua=mailto:${var.dmarc_rua}; ruf=mailto:${var.dmarc_rua}; fo=1; adkim=s; aspf=s"

  caa_rrdatas = concat(
    [for ca in var.caa_issuers : "0 issue \"${ca}\""],
    ["0 iodef \"mailto:${var.dmarc_rua}\""],
  )

  # app records minus apex TXT (folded above), normalized to FQDN names.
  app_rest = [for r in var.app_records : {
    name    = r.name == "@" ? local.dns_name : "${r.name}.${local.dns_name}"
    type    = upper(r.type)
    ttl     = r.ttl
    rrdatas = r.rrdatas
    } if !(r.name == "@" && upper(r.type) == "TXT")
  ]

  baseline = concat(
    length(local.apex_txt_all) > 0 ? [{ name = local.dns_name, type = "TXT", ttl = 3600, rrdatas = local.apex_txt_all }] : [],
    length(local.mx_rrdatas) > 0 ? [{ name = local.dns_name, type = "MX", ttl = 3600, rrdatas = local.mx_rrdatas }] : [],
    [{ name = "_dmarc.${local.dns_name}", type = "TXT", ttl = 3600, rrdatas = ["\"${local.dmarc_value}\""] }],
    [{ name = local.dns_name, type = "CAA", ttl = 3600, rrdatas = local.caa_rrdatas }],
    [for ext in var.report_authorizations : {
      name = "${ext}._report._dmarc.${local.dns_name}", type = "TXT", ttl = 3600, rrdatas = ["\"v=DMARC1\""]
    }],
  )

  # Redirect A records (apex + www) when a redirect target IP is provided for a redirect domain.
  redirect_records = var.role == "redirect" && var.redirect_ip != "" ? [
    { name = local.dns_name, type = "A", ttl = 300, rrdatas = [var.redirect_ip] },
    { name = "www.${local.dns_name}", type = "A", ttl = 300, rrdatas = [var.redirect_ip] },
  ] : []

  records = concat(local.baseline, local.redirect_records, local.app_rest)

  # A domain is safe to delegate once it has records beyond the security baseline:
  # explicit app_records, or emitted redirect A records.
  has_delegable_records = length(var.app_records) > 0 || length(local.redirect_records) > 0
}
