output "mail_fqdn" {
  value = local.mail
}

output "imap_fqdn" {
  value = local.imap
}

output "records_file" {
  value       = local_file.dns_records.filename
  description = "Path to the generated DNS record set to paste into the provider (or feed a provider resource)."
}

output "caldav_fqdn" {
  value = local.caldav
}

output "minio_fqdn" {
  value = local.minio
}

output "argocd_fqdn" {
  value = local.argocd
}
