# Fixed egress IP for outbound API calls that require an allowlisted source (e.g. the
# Namecheap API). Reserved external address(es) + Cloud Router + Cloud NAT with MANUAL_ONLY
# allocation so the egress IP is stable and can be pre-authorized at the registrar.

resource "google_compute_address" "egress" {
  count        = var.num_static_ips
  name         = "${var.name_prefix}-ip-${count.index}"
  project      = var.project
  region       = var.region
  address_type = "EXTERNAL"
}

resource "google_compute_router" "egress" {
  name    = "${var.name_prefix}-router"
  project = var.project
  region  = var.region
  network = var.network
}

resource "google_compute_router_nat" "egress" {
  name                               = "${var.name_prefix}-nat"
  project                            = var.project
  region                             = var.region
  router                             = google_compute_router.egress.name
  nat_ip_allocate_option             = "MANUAL_ONLY"
  nat_ips                            = google_compute_address.egress[*].self_link
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  dynamic "log_config" {
    for_each = var.log_nat ? [1] : []
    content {
      enable = true
      filter = "ERRORS_ONLY"
    }
  }
}
