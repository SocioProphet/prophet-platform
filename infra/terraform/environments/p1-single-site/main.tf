# p1-single-site — Hetzner Cloud k3s cluster
# Prerequisites: hcloud CLI, terraform, age/SOPS
# Usage: cp terraform.tfvars.example terraform.tfvars && terraform init && terraform apply

terraform {
  backend "s3" {
    # Bucket provisioned by infra/terraform/bootstrap — versioning + AES256 enabled there.
    bucket         = "prophet-terraform-state"
    key            = "p1-single-site/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "prophet-terraform-locks"
    encrypt        = true
    # For Hetzner Object Storage (S3-compatible):
    # endpoint         = "https://fsn1.your-objectstorage.com"
    # force_path_style = true
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "hcloud_token" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "ash"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key contents (not path)"
}

variable "domain" {
  type    = string
  default = "socioprophet.ai"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "minio_secret_key" {
  type      = string
  sensitive = true
}

variable "control_plane_type" {
  type    = string
  default = "cpx31"
}

variable "worker_type" {
  type    = string
  default = "cpx21"
}

variable "worker_count" {
  type    = number
  default = 2
}

# ── Core resources ────────────────────────────────────────────────────────────

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

resource "hcloud_ssh_key" "prophet" {
  name       = "prophet-p1"
  public_key = var.ssh_public_key
}

resource "hcloud_network" "main" {
  name     = "prophet-p1-net"
  ip_range = "10.10.0.0/16"
  labels = {
    "prophet.ai/env"        = "p1-single-site"
    "prophet.ai/managed-by" = "terraform"
  }
}

resource "hcloud_network_subnet" "nodes" {
  type         = "cloud"
  network_id   = hcloud_network.main.id
  network_zone = "us-east"
  ip_range     = "10.10.1.0/24"
}

resource "hcloud_firewall" "nodes" {
  name = "prophet-p1-nodes"
  labels = {
    "prophet.ai/env"        = "p1-single-site"
    "prophet.ai/managed-by" = "terraform"
  }

  rule {
    description = "SSH"
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "k8s API"
    direction   = "in"
    protocol    = "tcp"
    port        = "6443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "HTTP"
    direction   = "in"
    protocol    = "tcp"
    port        = "80"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "HTTPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "443"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "IMAP"
    direction   = "in"
    protocol    = "tcp"
    port        = "143"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "IMAPS"
    direction   = "in"
    protocol    = "tcp"
    port        = "993"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "SMTP submission"
    direction   = "in"
    protocol    = "tcp"
    port        = "587"
    source_ips  = ["0.0.0.0/0", "::/0"]
  }
  rule {
    description = "Flannel VXLAN (intra-cluster)"
    direction   = "in"
    protocol    = "udp"
    port        = "8472"
    source_ips  = ["10.10.0.0/16"]
  }
  rule {
    description = "kubelet metrics (intra-cluster)"
    direction   = "in"
    protocol    = "tcp"
    port        = "10250"
    source_ips  = ["10.10.0.0/16"]
  }
}

# ── Control plane node ────────────────────────────────────────────────────────

module "control_plane" {
  source = "../../modules/k3s-node"

  name               = "prophet-p1-control-0"
  server_type        = var.control_plane_type
  location           = var.location
  ssh_public_key_id  = hcloud_ssh_key.prophet.id
  private_network_id = hcloud_network.main.id
  private_ip         = "10.10.1.10"
  firewall_ids       = [hcloud_firewall.nodes.id]
  role               = "control-plane"
  k3s_token          = random_password.k3s_token.result
  k3s_server_url     = ""
  extra_k3s_args     = "--tls-san ${hcloud_server.control_plane_placeholder.ipv4_address}"

  depends_on = [hcloud_network_subnet.nodes]
}

# Placeholder to get the IP before cloud-init runs (chicken-and-egg workaround)
resource "hcloud_server" "control_plane_placeholder" {
  name        = "prophet-p1-control-0-ip-probe"
  server_type = "cx11"
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = [hcloud_ssh_key.prophet.id]
  lifecycle { ignore_changes = [user_data, labels] }
}

# ── Worker nodes ──────────────────────────────────────────────────────────────

module "workers" {
  count  = var.worker_count
  source = "../../modules/k3s-node"

  name               = "prophet-p1-worker-${count.index}"
  server_type        = var.worker_type
  location           = var.location
  ssh_public_key_id  = hcloud_ssh_key.prophet.id
  private_network_id = hcloud_network.main.id
  private_ip         = "10.10.1.${20 + count.index}"
  firewall_ids       = [hcloud_firewall.nodes.id]
  role               = "worker"
  k3s_token          = random_password.k3s_token.result
  k3s_server_url     = "https://${module.control_plane.private_ip}:6443"

  depends_on = [module.control_plane]
}

# ── Secrets ───────────────────────────────────────────────────────────────────

module "workspace_secrets" {
  source            = "../../modules/workspace-secrets"
  env               = "p1-single-site"
  postgres_password = var.postgres_password
  minio_secret_key  = var.minio_secret_key
  k3s_token         = random_password.k3s_token.result
}

# ── DNS records ───────────────────────────────────────────────────────────────

module "dns" {
  source           = "../../modules/dns"
  zone_name        = var.domain
  control_plane_ip = module.control_plane.public_ipv4
  subdomain_prefix = ""
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "control_plane_ip" {
  value = module.control_plane.public_ipv4
}

output "worker_ips" {
  value = [for w in module.workers : w.public_ipv4]
}

output "k8s_api_url" {
  value = "https://${module.control_plane.public_ipv4}:6443"
}

output "mail_fqdn" {
  value = module.dns.mail_fqdn
}

output "caldav_fqdn" {
  value = module.dns.caldav_fqdn
}

output "minio_fqdn" {
  value = module.dns.minio_fqdn
}

output "secrets_dir" {
  value     = module.workspace_secrets.secrets_dir
  sensitive = true
}
