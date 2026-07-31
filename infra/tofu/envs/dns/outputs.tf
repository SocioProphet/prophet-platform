output "name_servers" {
  description = "Per-domain Cloud DNS name servers. Delegate each domain to these at the registrar (or set var.manage_registrar=true to do it via Namecheap)."
  value       = { for k, m in module.zone : k => m.name_servers }
}

output "zones" {
  description = "Managed zone resource names, keyed by domain."
  value       = { for k, m in module.zone : k => m.zone_name }
}

output "egress_ips" {
  description = "Static egress IP(s) to allowlist in Namecheap and set as namecheap_client_ip. Empty unless create_egress_nat=true."
  value       = var.create_egress_nat ? module.egress_nat[0].egress_ips : []
}
