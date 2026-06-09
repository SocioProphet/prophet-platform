# Local environment — provider-agnostic
# Provisions a k3d cluster for local development.
# No cloud provider required. No state backend — local file.
# Maps to p0-lab overlay in infra/k8s/overlays/p0-lab/.

terraform {
  backend "local" {
    path = ".terraform/local.tfstate"
  }
}

variable "cluster_name" { type = string; default = "prophet-local" }
variable "k3d_agents"   { type = number; default = 2 }
variable "api_port"     { type = number; default = 6550 }

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

resource "local_file" "k3d_config" {
  filename = "${path.root}/k3d-config.yaml"
  content  = <<-YAML
    apiVersion: k3d.io/v1alpha5
    kind: Simple
    metadata:
      name: ${var.cluster_name}
    servers: 1
    agents: ${var.k3d_agents}
    kubeAPI:
      hostPort: "${var.api_port}"
    ports:
      - port: 8080:80
        nodeFilters: [loadbalancer]
      - port: 8443:443
        nodeFilters: [loadbalancer]
      - port: 143:143
        nodeFilters: [loadbalancer]
      - port: 587:587
        nodeFilters: [loadbalancer]
      - port: 5232:5232
        nodeFilters: [loadbalancer]
      - port: 9000:9000
        nodeFilters: [loadbalancer]
    options:
      k3s:
        extraArgs:
          - arg: --disable=traefik
            nodeFilters: [server:*]
  YAML
}

resource "null_resource" "k3d_cluster" {
  depends_on = [local_file.k3d_config]
  triggers   = { config_hash = local_file.k3d_config.content }

  provisioner "local-exec" {
    command = <<-SH
      if k3d cluster list | grep -q '${var.cluster_name}'; then
        echo "cluster ${var.cluster_name} already exists"
      else
        k3d cluster create --config ${path.root}/k3d-config.yaml
      fi
      k3d kubeconfig merge ${var.cluster_name} --kubeconfig-switch-context
    SH
  }

  provisioner "local-exec" {
    when    = destroy
    command = "k3d cluster delete ${var.cluster_name} || true"
  }
}

output "kubeconfig_context" { value = "k3d-${var.cluster_name}" }
output "k3s_token"          { value = random_password.k3s_token.result; sensitive = true }
