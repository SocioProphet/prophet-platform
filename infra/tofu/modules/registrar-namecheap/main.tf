# Delegates a Namecheap domain's nameservers to Cloud DNS. Registrar-only: this module
# never manages host records (those live in Cloud DNS). Custom nameservers and host
# records are mutually exclusive at Namecheap, so setting NS here hands DNS to Cloud DNS.

resource "namecheap_domain_records" "delegation" {
  count       = var.enabled ? 1 : 0
  domain      = var.domain
  mode        = "OVERWRITE"
  nameservers = var.name_servers
}
