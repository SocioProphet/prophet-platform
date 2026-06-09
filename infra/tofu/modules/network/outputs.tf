output "vpc_id"           { value = google_compute_network.vpc.id }
output "vpc_self_link"    { value = google_compute_network.vpc.self_link }
output "subnet_self_links" {
  value = { for k, v in google_compute_subnetwork.subnets : k => v.self_link }
}
output "subnet_names" {
  value = { for k, v in google_compute_subnetwork.subnets : k => v.name }
}
