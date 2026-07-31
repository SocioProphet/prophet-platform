output "ip_address" {
  description = "The redirect LB's global IP. Point redirect domains' apex/www A records here."
  value       = google_compute_global_address.this.address
}

output "cert_domains" {
  description = "Domains the managed cert covers."
  value       = var.cert_domains
}
