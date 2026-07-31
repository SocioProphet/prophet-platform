output "name_servers" {
  description = "Route53 name servers to delegate this domain to at the registrar."
  value       = aws_route53_zone.this.name_servers
}

output "zone_name" {
  description = "Route53 hosted zone id."
  value       = aws_route53_zone.this.zone_id
}
