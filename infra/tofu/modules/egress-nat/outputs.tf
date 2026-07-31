output "egress_ips" {
  description = "Reserved static egress IP(s). Allowlist in the Namecheap API settings and set as namecheap_client_ip."
  value       = google_compute_address.egress[*].address
}

output "router_name" {
  description = "Cloud Router name."
  value       = google_compute_router.egress.name
}

output "nat_name" {
  description = "Cloud NAT name."
  value       = google_compute_router_nat.egress.name
}
