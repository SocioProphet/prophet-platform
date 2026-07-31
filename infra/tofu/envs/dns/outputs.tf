output "name_servers" {
  description = "Per-domain Cloud DNS name servers. Delegate each domain to these at the registrar (or set var.manage_registrar=true to do it via Namecheap)."
  value       = { for k, m in module.zone : k => m.name_servers }
}

output "zones" {
  description = "Managed zone resource names, keyed by domain."
  value       = { for k, m in module.zone : k => m.zone_name }
}
