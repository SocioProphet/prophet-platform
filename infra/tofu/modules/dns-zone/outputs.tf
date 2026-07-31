output "name_servers" {
  description = "Cloud DNS name servers to delegate this domain to at the registrar."
  value       = google_dns_managed_zone.this.name_servers
}

output "zone_name" {
  description = "The managed zone resource name."
  value       = google_dns_managed_zone.this.name
}

output "dns_name" {
  description = "The zone dns_name (with trailing dot)."
  value       = google_dns_managed_zone.this.dns_name
}
