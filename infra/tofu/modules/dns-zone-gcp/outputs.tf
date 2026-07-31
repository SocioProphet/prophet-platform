output "name_servers" {
  description = "Cloud DNS name servers to delegate this domain to at the registrar."
  value       = google_dns_managed_zone.this.name_servers
}

output "zone_name" {
  description = "Managed zone resource name."
  value       = google_dns_managed_zone.this.name
}
