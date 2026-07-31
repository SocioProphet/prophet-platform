# AWS emitter: renders the SAME normalized record model onto Route53. This proves the
# cloud-agnostic seam — it consumes dns-records output with no changes to that model.
# Reference emitter: validate against a real AWS account before production use.

resource "aws_route53_zone" "this" {
  name = var.dns_name
  tags = merge({
    role       = var.role
    managed_by = "tofu-dns-portfolio"
  }, var.labels)

  lifecycle {
    precondition {
      # Fail closed: never silently drop DNSSEC. Route53 DNSSEC needs a KMS KSK + zone
      # signing resources not implemented in this emitter yet.
      condition     = !var.dnssec
      error_message = "AWS emitter does not implement DNSSEC yet (needs a KMS key-signing key). Set dnssec=false for AWS domains, or use the GCP emitter, or extend this module."
    }
  }
}

resource "aws_route53_record" "this" {
  for_each = { for r in var.records : "${r.type} ${r.name}" => r }
  zone_id  = aws_route53_zone.this.zone_id
  name     = each.value.name
  type     = each.value.type
  ttl      = each.value.ttl
  records  = each.value.rrdatas
}
