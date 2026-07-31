# DNS portfolio — one Cloud DNS zone per owned domain, driven by domains.yaml.
#
# APPLY GATE (same doctrine as envs/gcp-landing):
#   plan-only in CI; no apply without manual GH Actions environment approval + signed plan.
#   Registrar NS delegation stays OFF (var.manage_registrar=false) until a plan is reviewed
#   and the Namecheap API client_ip is allowlisted (see README).

provider "google" {
  project = var.project
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
}

module "zone" {
  source   = "../../modules/dns-zone"
  for_each = local.domains

  domain       = each.value.domain
  role         = each.value.role
  mail         = try(each.value.mail, false)
  dnssec       = try(each.value.dnssec, true)
  dmarc_rua    = var.dmarc_rua
  dmarc_policy = try(each.value.dmarc_policy, "")
  spf          = try(each.value.spf, "")
  mx_records   = try(each.value.mx, [])
  app_records  = try(each.value.records, [])
}

module "registrar" {
  source   = "../../modules/registrar-namecheap"
  for_each = { for k, d in local.domains : k => d if try(d.manage_ns, false) }

  domain       = each.value.domain
  name_servers = module.zone[each.key].name_servers
  enabled      = var.manage_registrar
}
