# DNS module — emit a records.tf.json file for manual import into your DNS provider.
# Swap this for a real provider (cloudflare, route53, hcloud_dns) once API tokens are wired.

locals {
  fqdn   = var.subdomain_prefix != "" ? "${var.subdomain_prefix}.${var.zone_name}" : var.zone_name
  # Workspace service FQDNs
  mail   = "mail.${local.fqdn}"
  caldav = "caldav.${local.fqdn}"
  minio  = "storage.${local.fqdn}"
  argocd = "argocd.${local.fqdn}"
}

resource "local_file" "dns_records" {
  filename = "${path.root}/dns-records.txt"
  content  = <<-TXT
    # DNS records to create in your provider
    # Zone: ${var.zone_name}
    # Control-plane IP: ${var.control_plane_ip}

    ${local.mail}    A  ${var.control_plane_ip}
    ${local.caldav}  A  ${var.control_plane_ip}
    ${local.minio}   A  ${var.control_plane_ip}
    ${local.argocd}  A  ${var.control_plane_ip}

    # IMAP/SMTP MX / SRV records (add in DNS console):
    # _imap._tcp.${local.fqdn}  SRV 0 1 143 ${local.mail}
    # _imaps._tcp.${local.fqdn} SRV 0 1 993 ${local.mail}
    # _submission._tcp.${local.fqdn} SRV 0 1 587 ${local.mail}
    # _caldavs._tcp.${local.fqdn} SRV 0 1 443 ${local.caldav}
    # _carddavs._tcp.${local.fqdn} SRV 0 1 443 ${local.caldav}
    MX  ${var.zone_name}  10  ${local.mail}
    TXT ${var.zone_name}  "v=spf1 a:${local.mail} ~all"
  TXT
}
