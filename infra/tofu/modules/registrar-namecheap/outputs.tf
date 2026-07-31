output "delegated" {
  description = "Whether NS delegation was applied for this domain."
  value       = var.enabled
}

output "name_servers" {
  description = "The nameservers requested for this domain."
  value       = var.name_servers
}
