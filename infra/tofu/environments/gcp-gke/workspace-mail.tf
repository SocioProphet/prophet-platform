# Workspace mail plane — cloud-side infra (the parts that must NOT be a manual runbook).
# Static egress/ingress IPs for the SMTP + IMAP LoadBalancers, and cert-manager for auto-renewing
# TLS. The k8s LoadBalancer Services that bind these IPs live in the GitOps kustomize tree
# (infra/k8s/workspace-mail) so ArgoCD owns app-layer resources; here we own the cloud primitives.
#
# IMPORT (these two were reserved imperatively to unblock — adopt them into state, do not recreate):
#   tofu import google_compute_address.ws_smtp projects/socioprophet-platform/regions/us-central1/addresses/ws-smtp
#   tofu import google_compute_address.ws_imap projects/socioprophet-platform/regions/us-central1/addresses/ws-imap

resource "google_compute_address" "ws_smtp" {
  name         = "ws-smtp"
  description  = "mail.socioprophet.ai — SMTP LoadBalancer (25/587) + MX target. Set PTR on this IP."
  region       = var.region
  address_type = "EXTERNAL"
  labels       = local.labels
}

resource "google_compute_address" "ws_imap" {
  name         = "ws-imap"
  description  = "imap.socioprophet.ai — IMAPS LoadBalancer (993)."
  region       = var.region
  address_type = "EXTERNAL"
  labels       = local.labels
}

# cert-manager — auto-renewing TLS for the L4 mail endpoints (GKE ManagedCertificates only work on
# HTTP(S) ingress, not the L4 SMTP/IMAP LoadBalancers, so cert-manager is the sovereign choice here).
resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = "v1.16.2"

  set {
    name  = "crds.enabled"
    value = "true"
  }

  depends_on = [helm_release.argocd]
}

# ACME issuer via DNS-01. mail.* / imap.* are L4, so HTTP-01 is not an option — DNS-01 is required.
# socioprophet.ai is authoritative at Namecheap (manual), so cert-manager cannot write _acme-challenge
# there directly. The sovereign, fully-automatable path is CNAME-delegation to Google Cloud DNS:
#   1. Create a Cloud DNS managed zone (e.g. acme.socioprophet.ai) — set acme_delegation_zone below.
#   2. One-time at Namecheap: CNAME  _acme-challenge.mail  ->  _acme-challenge.mail.acme.socioprophet.ai
#                             CNAME  _acme-challenge.imap  ->  _acme-challenge.imap.acme.socioprophet.ai
#   3. cert-manager's clouddns solver answers in the delegated zone using Workload Identity.
# Left DISABLED until the delegation zone exists, so we never ship a half-configured issuer.
variable "acme_email" {
  type        = string
  default     = ""
  description = "Contact email for Let's Encrypt (required to enable the ClusterIssuer)."
}

variable "acme_dns01_project" {
  type        = string
  default     = ""
  description = "GCP project holding the Cloud DNS delegation zone for DNS-01. Empty = ClusterIssuer not created."
}

resource "helm_release" "mail_acme_issuer" {
  count = var.acme_email != "" && var.acme_dns01_project != "" ? 1 : 0

  name      = "mail-acme-issuer"
  namespace = "cert-manager"
  chart     = "raw"
  # A tiny raw chart to carry one ClusterIssuer manifest through the same provider pattern.
  repository = "https://bedag.github.io/helm-charts/"
  version    = "2.0.0"

  values = [yamlencode({
    resources = [{
      apiVersion = "cert-manager.io/v1"
      kind       = "ClusterIssuer"
      metadata   = { name = "letsencrypt-dns01" }
      spec = {
        acme = {
          email               = var.acme_email
          server              = "https://acme-v02.api.letsencrypt.org/directory"
          privateKeySecretRef = { name = "letsencrypt-dns01-account" }
          solvers = [{
            dns01 = { cloudDNS = { project = var.acme_dns01_project } }
          }]
        }
      }
    }]
  })]

  depends_on = [helm_release.cert_manager]
}

output "ws_smtp_ip" {
  value       = google_compute_address.ws_smtp.address
  description = "mail.socioprophet.ai A record + MX target; set PTR here."
}

output "ws_imap_ip" {
  value       = google_compute_address.ws_imap.address
  description = "imap.socioprophet.ai A record."
}
