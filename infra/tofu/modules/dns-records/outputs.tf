output "zone_name" {
  description = "RFC1035-safe zone name (domain with dots as hyphens)."
  value       = local.zone_name
}

output "dns_name" {
  description = "Zone dns_name with trailing dot."
  value       = local.dns_name
}

output "dnssec" {
  description = "Whether the emitter should sign the zone."
  value       = var.dnssec
}

output "records" {
  description = "Normalized records: list of { name, type, ttl, rrdatas }. Cloud-agnostic; consumed by any emitter."
  value       = local.records
}

output "has_app_records" {
  description = "Whether explicit app_records were supplied."
  value       = length(var.app_records) > 0
}

output "has_delegable_records" {
  description = "Whether the domain has records beyond the security baseline (app_records or emitted redirect A records). Used to fail-closed on delegating an otherwise-empty canonical/redirect domain."
  value       = local.has_delegable_records
}
