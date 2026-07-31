# GCP emitter: renders the normalized record model onto Google Cloud DNS.

resource "google_dns_managed_zone" "this" {
  name        = var.zone_name
  dns_name    = var.dns_name
  description = "Managed by tofu envs/dns — role=${var.role}"
  labels = merge({
    role       = var.role
    managed_by = "tofu-dns-portfolio"
  }, var.labels)

  dynamic "dnssec_config" {
    for_each = var.dnssec ? [1] : []
    content {
      state = "on"
    }
  }
}

resource "google_dns_record_set" "this" {
  for_each     = { for r in var.records : "${r.type} ${r.name}" => r }
  name         = each.value.name
  type         = each.value.type
  ttl          = each.value.ttl
  managed_zone = google_dns_managed_zone.this.name
  rrdatas      = each.value.rrdatas
}
