resource "google_compute_network" "vpc" {
  project                 = var.host_project_id
  name                    = "prophet-platform-vpc"
  auto_create_subnetworks = false
  routing_mode            = "GLOBAL"
}

resource "google_compute_subnetwork" "subnets" {
  for_each = var.subnets

  project       = var.host_project_id
  name          = "prophet-${each.key}"
  network       = google_compute_network.vpc.id
  region        = var.region
  ip_cidr_range = each.value.cidr
  description   = each.value.description

  dynamic "secondary_ip_range" {
    for_each = each.value.secondary_ranges
    content {
      range_name    = secondary_ip_range.key
      ip_cidr_range = secondary_ip_range.value
    }
  }

  private_ip_google_access = true
  log_config { aggregation_interval = "INTERVAL_5_SEC"; flow_sampling = 0.5; metadata = "INCLUDE_ALL_METADATA" }
}

# Private Google Access — allows GKE nodes to reach GCP APIs without external IPs
resource "google_compute_router" "router" {
  project = var.host_project_id
  name    = "prophet-router"
  region  = var.region
  network = google_compute_network.vpc.id
}

resource "google_compute_router_nat" "nat" {
  project                            = var.host_project_id
  name                               = "prophet-nat"
  router                             = google_compute_router.router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  log_config { enable = true; filter = "ERRORS_ONLY" }
}

# Shared VPC service project attachments
resource "google_compute_shared_vpc_service_project" "attachments" {
  for_each        = toset(var.shared_vpc_service_projects)
  host_project    = var.host_project_id
  service_project = each.value
}
