resource "hcloud_server" "node" {
  name        = var.name
  server_type = var.server_type
  location    = var.location
  image       = var.image
  ssh_keys     = [var.ssh_public_key_id]
  firewall_ids = var.firewall_ids

  network {
    network_id = var.private_network_id
    ip         = var.private_ip
  }

  user_data = templatefile("${path.module}/cloud-init.tpl", {
    k3s_version    = var.k3s_version
    k3s_token      = var.k3s_token
    k3s_server_url = var.k3s_server_url
    role           = var.role
    extra_args     = var.extra_k3s_args
    node_name      = var.name
  })

  labels = {
    "prophet.ai/env"  = "p1-single-site"
    "prophet.ai/role" = var.role
  }
}
