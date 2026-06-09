output "server_id" {
  value = hcloud_server.node.id
}

output "public_ipv4" {
  value = hcloud_server.node.ipv4_address
}

output "private_ip" {
  value = var.private_ip
}

output "name" {
  value = hcloud_server.node.name
}
