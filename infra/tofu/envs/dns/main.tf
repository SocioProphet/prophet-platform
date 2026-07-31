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
  has_records  = module.records[each.key].has_app_records
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
