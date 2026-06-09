# p0-lab — local k3d cluster + local state
# Prerequisites: k3d, kubectl, docker daemon running
# Usage: terraform init && terraform apply

terraform {
  backend "local" {
    path = ".terraform/p0-lab.tfstate"
  }
}

variable "k3d_cluster_name" {
  type    = string
  default = "prophet-p0-lab"
}

variable "k3d_agents" {
  type    = number
  default = 2
}

variable "k3d_api_port" {
  type    = number
  default = 6550
}

variable "postgres_password" {
  type      = string
  sensitive = true
  default   = "prophet-dev"
}

variable "minio_secret_key" {
  type      = string
  sensitive = true
  default   = "prophet-minio-dev"
}

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

# Write a k3d config file and create the cluster via null_resource
resource "local_file" "k3d_config" {
  filename = "${path.root}/k3d-config.yaml"
  content  = <<-YAML
    apiVersion: k3d.io/v1alpha5
    kind: Simple
    metadata:
      name: ${var.k3d_cluster_name}
    servers: 1
    agents: ${var.k3d_agents}
    kubeAPI:
      hostPort: "${var.k3d_api_port}"
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

  triggers = {
    cluster_name = var.k3d_cluster_name
    config_hash  = local_file.k3d_config.content
  }

  provisioner "local-exec" {
    command = <<-SH
      if k3d cluster list | grep -q '${var.k3d_cluster_name}'; then
        echo "cluster ${var.k3d_cluster_name} already exists, skipping create"
      else
        k3d cluster create --config ${path.root}/k3d-config.yaml
      fi
      k3d kubeconfig merge ${var.k3d_cluster_name} --kubeconfig-switch-context
    SH
  }

  provisioner "local-exec" {
    when    = destroy
    command = "k3d cluster delete ${self.triggers.cluster_name} || true"
  }
}

# Namespace
resource "null_resource" "namespace" {
  depends_on = [null_resource.k3d_cluster]
  provisioner "local-exec" {
    command = "kubectl apply -f ${path.root}/../../../k8s/namespaces/socioprophet.yaml"
  }
}

module "workspace_secrets" {
  source            = "../../modules/workspace-secrets"
  env               = "p0-lab"
  postgres_password = var.postgres_password
  minio_secret_key  = var.minio_secret_key
  k3s_token         = random_password.k3s_token.result
}

output "kubeconfig_context" {
  value = "k3d-${var.k3d_cluster_name}"
}

output "secrets_dir" {
  value     = module.workspace_secrets.secrets_dir
  sensitive = true
}
