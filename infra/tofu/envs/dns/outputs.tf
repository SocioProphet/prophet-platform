output "name_servers" {
  description = "Per-domain nameservers from the active cloud emitter. Delegate each domain to these at the registrar."
  value       = { for k in keys(local.domains) : k => try(module.gcp[k].name_servers, module.aws[k].name_servers, []) }
}

output "record_manifest" {
  description = "Audit artifact: the full normalized record set that WILL be created per domain (cloud-agnostic). Review via `tofu output -json record_manifest`."
  value       = { for k, m in module.records : k => m.records }
}

output "redirect_ip" {
  description = "Redirect LB IP (empty unless enable_redirects=true). Redirect domains' apex/www A records point here."
  value       = local.redirect_ip
}

output "egress_ips" {
  description = "Static egress IP(s) to allowlist in Namecheap and set as namecheap_client_ip. Empty unless create_egress_nat=true."
  value       = var.create_egress_nat ? module.egress_nat[0].egress_ips : []
}
