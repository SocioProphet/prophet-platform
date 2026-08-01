# DNS portfolio — cloud-agnostic record model (dns-records) rendered by a pluggable
# per-cloud emitter selected by var.dns_cloud. Adding a cloud = one new emitter against the
# dns-records contract; domains.yaml and the safety model never change.
#
# APPLY GATE (same doctrine as envs/gcp-landing): plan-only in CI; no apply without manual
# GH environment approval + signed plan. Registrar NS delegation stays OFF until reviewed
# and the Namecheap API client_ip is allowlisted (see BOOTSTRAP.md).

provider "google" {
  project = var.project
}

provider "aws" {
  region = var.aws_region
}

provider "namecheap" {
  user_name   = var.namecheap_user_name
  api_user    = var.namecheap_api_user
  api_key     = var.namecheap_api_key
  client_ip   = var.namecheap_client_ip
  use_sandbox = var.namecheap_sandbox
}

locals {
  cfg     = yamldecode(file("${path.module}/domains.yaml"))
  domains = { for d in local.cfg.domains : d.domain => d }

  # rua domain hosts the DMARC aggregate-report authorizations for every other domain.
  rua_domain          = split("@", var.dmarc_rua)[1]
  report_auth_targets = [for d in keys(local.domains) : d if d != local.rua_domain]

  # Redirect plane: redirect-role domains 301 to a canonical target (default or per-domain).
  redirects_map         = { for k, d in local.domains : d.domain => try(d.redirect_to, var.default_redirect_target) if d.role == "redirect" }
  redirect_cert_domains = flatten([for k, d in local.domains : [d.domain, "www.${d.domain}"] if d.role == "redirect"])
  redirects_enabled     = var.dns_cloud == "gcp" && var.enable_redirects && length(local.redirects_map) > 0
  redirect_ip           = try(module.web_redirect[0].ip_address, "")
}

# ── Cloud-agnostic record model (one per domain) ────────────────────────────────
module "records" {
  source   = "../../modules/dns-records"
  for_each = local.domains

  domain                = each.value.domain
  role                  = each.value.role
  mail                  = try(each.value.mail, false)
  dnssec                = try(each.value.dnssec, true)
  dmarc_rua             = var.dmarc_rua
  dmarc_policy          = try(each.value.dmarc_policy, "")
  spf                   = try(each.value.spf, "")
  mx_records            = try(each.value.mx, [])
  app_records           = try(each.value.records, [])
  report_authorizations = each.key == local.rua_domain ? local.report_auth_targets : []
  redirect_ip           = local.redirect_ip
}

# Redirect service (GCP): 301s redirect-role domains to their canonical target. Off by
# default; a portable sibling (e.g. web-redirect-aws) would satisfy the same ip_address contract.
module "web_redirect" {
  source         = "../../modules/web-redirect-gcp"
  count          = local.redirects_enabled ? 1 : 0
  project        = var.project
  redirects      = local.redirects_map
  default_target = var.default_redirect_target
  cert_domains   = local.redirect_cert_domains
}

# ── Pluggable emitters (only the selected cloud is instantiated) ─────────────────
module "gcp" {
  source   = "../../modules/dns-zone-gcp"
  for_each = var.dns_cloud == "gcp" ? local.domains : {}

  zone_name = module.records[each.key].zone_name
  dns_name  = module.records[each.key].dns_name
  dnssec    = module.records[each.key].dnssec
  role      = each.value.role
  records   = module.records[each.key].records
}

module "aws" {
  source   = "../../modules/dns-zone-aws"
  for_each = var.dns_cloud == "aws" ? local.domains : {}

  zone_name = module.records[each.key].zone_name
  dns_name  = module.records[each.key].dns_name
  dnssec    = module.records[each.key].dnssec
  role      = each.value.role
  records   = module.records[each.key].records
}

# ── Registrar NS delegation (guarded; fail-closed) ───────────────────────────────
module "registrar" {
  source   = "../../modules/registrar-namecheap"
  for_each = { for k, d in local.domains : k => d if try(d.manage_ns, false) }

  domain       = each.value.domain
  name_servers = try(module.gcp[each.key].name_servers, module.aws[each.key].name_servers, [])
  role         = each.value.role
  has_records  = module.records[each.key].has_delegable_records
  enabled      = var.manage_registrar
}

# ── Optional static egress IP for the Namecheap API allowlist ────────────────────
module "egress_nat" {
  source  = "../../modules/egress-nat"
  count   = var.create_egress_nat ? 1 : 0
  project = var.project
  region  = var.egress_region
  network = var.egress_network
}
