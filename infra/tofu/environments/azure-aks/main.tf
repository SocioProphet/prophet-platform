# Azure AKS substrate — the cloud-specific half of the platform. The app layer
# (charts/ + deploy/argocd) is identical to every other cloud; only this cluster
# + registry differ. Mirrors infra/tofu/environments/gcp-gke.

locals {
  prophet_tags = {
    "prophet.ai/managed-by" = "opentofu"
    "prophet.ai/env"        = var.cluster_name
    "org"                   = "socioprophet"
    "source-of-truth"       = "git"
  }
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group
  location = var.location
  tags     = local.prophet_tags
}

# Container registry (the AKS equivalent of GAR).
resource "azurerm_container_registry" "this" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "Standard"
  admin_enabled       = false
  tags                = local.prophet_tags
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = var.cluster_name
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  dns_prefix          = var.cluster_name
  tags                = local.prophet_tags

  # Enable OIDC issuer + Workload Identity so pods federate via projected tokens (no static creds).
  oidc_issuer_enabled       = true
  workload_identity_enabled = true

  default_node_pool {
    name       = "system"
    node_count = 2
    vm_size    = "Standard_D2s_v5"
  }

  identity {
    type = "SystemAssigned"
  }
}

# GPU pool for finetuning / model training. Scales 0→N so it costs nothing idle;
# workloads request it via the nvidia.com/gpu taint toleration.
resource "azurerm_kubernetes_cluster_node_pool" "gpu" {
  name                  = "gpu"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = "Standard_NC4as_T4_v3"
  auto_scaling_enabled  = true
  node_count            = 0
  min_count             = 0
  max_count             = var.gpu_max_nodes
  node_taints           = ["nvidia.com/gpu=present:NoSchedule"]
  tags                  = local.prophet_tags
}

# Let the cluster pull images from ACR.
resource "azurerm_role_assignment" "acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.this.kubelet_identity[0].object_id
}

# Workload Identity — no static credentials in pods (ADR-050 Azure equivalent)
module "workload_identity" {
  source          = "../../modules/azure-workload-identity"
  cluster_name    = var.cluster_name
  resource_group  = azurerm_resource_group.this.name
  location        = azurerm_resource_group.this.location
  oidc_issuer_url = azurerm_kubernetes_cluster.this.oidc_issuer_url
  tags            = local.prophet_tags

  bindings = {
    argocd-deployer = {
      k8s_namespace    = "argocd"
      k8s_sa_name      = "argocd-server"
      scope            = azurerm_kubernetes_cluster.this.id
      role_definitions = ["Azure Kubernetes Service Cluster User Role"]
    }
    tekton-builder = {
      k8s_namespace    = "tekton-pipelines"
      k8s_sa_name      = "tekton-builder"
      scope            = azurerm_container_registry.this.id
      role_definitions = ["AcrPush"]
    }
  }
}

# GitHub Actions OIDC — CI gets a federated identity, no static credentials
module "github_ci" {
  source             = "../../modules/github-oidc-azure"
  cluster_name       = var.cluster_name
  resource_group     = azurerm_resource_group.this.name
  location           = azurerm_resource_group.this.location
  github_repo        = "SocioProphet/prophet-platform"
  subscription_scope = "/subscriptions/${var.subscription_id}"
  cluster_scope      = azurerm_kubernetes_cluster.this.id
  tags               = local.prophet_tags
}
