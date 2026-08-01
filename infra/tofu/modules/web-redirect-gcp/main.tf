# Global external Application LB that 301-redirects each host to its canonical target.
# GCP-specific by nature (an L7 redirect service); the redirect INTENT stays portable in
# domains.yaml and the A records flow through the agnostic dns-records model. An AWS
# equivalent (CloudFront function / S3 redirect) would be a sibling module with the same
# ip_address/output contract.
#
# NOTE: the Google-managed cert provisions only AFTER the domains' A records point at this
# LB's IP (chicken-and-egg is expected) — allow ~15–60 min after the first apply.

locals {
  targets      = distinct(values(var.redirects))
  matcher_name = { for t in local.targets : t => "m-${replace(t, ".", "-")}" }
}

resource "google_compute_global_address" "this" {
  name    = "${var.name_prefix}-ip"
  project = var.project
}

resource "google_compute_managed_ssl_certificate" "this" {
  name    = "${var.name_prefix}-cert"
  project = var.project
  managed {
    domains = var.cert_domains
  }
}

resource "google_compute_url_map" "https_redirect" {
  name    = "${var.name_prefix}-https-urlmap"
  project = var.project

  default_url_redirect {
    host_redirect          = var.default_target
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }

  dynamic "host_rule" {
    for_each = var.redirects
    content {
      hosts        = [host_rule.key]
      path_matcher = local.matcher_name[host_rule.value]
    }
  }

  dynamic "path_matcher" {
    for_each = toset(local.targets)
    content {
      name = local.matcher_name[path_matcher.value]
      default_url_redirect {
        host_redirect          = path_matcher.value
        https_redirect         = true
        redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
        strip_query            = false
      }
    }
  }
}

resource "google_compute_target_https_proxy" "this" {
  name             = "${var.name_prefix}-https-proxy"
  project          = var.project
  url_map          = google_compute_url_map.https_redirect.id
  ssl_certificates = [google_compute_managed_ssl_certificate.this.id]
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.name_prefix}-https-fr"
  project               = var.project
  target                = google_compute_target_https_proxy.this.id
  ip_address            = google_compute_global_address.this.address
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# Port 80 -> 443 upgrade.
resource "google_compute_url_map" "http_to_https" {
  name    = "${var.name_prefix}-http-urlmap"
  project = var.project
  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "this" {
  name    = "${var.name_prefix}-http-proxy"
  project = var.project
  url_map = google_compute_url_map.http_to_https.id
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.name_prefix}-http-fr"
  project               = var.project
  target                = google_compute_target_http_proxy.this.id
  ip_address            = google_compute_global_address.this.address
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
