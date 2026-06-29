# IBM Cloud IKS substrate (VPC). Same platform, IBM underneath: a VPC IKS
# cluster (default pool + scale-capable GPU pool) + Container Registry namespace
# + Argo CD + the identical root app. App layer (charts/ + deploy/argocd)
# unchanged.

locals {
  prophet_tags = [
    "managed-by:opentofu",
    "environment:production",
    "team:platform",
    "repo:SocioProphet/prophet-platform",
  ]
}

data "ibm_resource_group" "this" {
  name = var.resource_group
}

resource "ibm_is_vpc" "this" {
  name = var.cluster_name
  tags = local.prophet_tags
}

resource "ibm_is_subnet" "this" {
  name                     = "${var.cluster_name}-subnet"
  vpc                      = ibm_is_vpc.this.id
  zone                     = var.zone
  total_ipv4_address_count = 256
  resource_group           = data.ibm_resource_group.this.id
  tags                     = local.prophet_tags
}

resource "ibm_container_vpc_cluster" "this" {
  name              = var.cluster_name
  vpc_id            = ibm_is_vpc.this.id
  kube_version      = var.kube_version
  flavor            = "bx2.4x16"
  worker_count      = 2
  resource_group_id = data.ibm_resource_group.this.id
  tags              = local.prophet_tags

  zones {
    subnet_id = ibm_is_subnet.this.id
    name      = var.zone
  }
}

# GPU pool for finetuning / model training.
resource "ibm_container_vpc_worker_pool" "gpu" {
  cluster           = ibm_container_vpc_cluster.this.id
  worker_pool_name  = "gpu"
  flavor            = var.gpu_flavor
  vpc_id            = ibm_is_vpc.this.id
  worker_count      = 0
  resource_group_id = data.ibm_resource_group.this.id

  zones {
    subnet_id = ibm_is_subnet.this.id
    name      = var.zone
  }
}

# Container registry namespace (the IBM equivalent of GAR).
resource "ibm_cr_namespace" "images" {
  name              = var.registry_namespace
  resource_group_id = data.ibm_resource_group.this.id
  tags              = local.prophet_tags
}

# GitHub Actions OIDC federation via IBM Trusted Profile (no static API keys).
# After apply, set IBM_TRUSTED_PROFILE_ID as a GitHub Actions *variable*.
module "github_ci" {
  source            = "../../modules/ibm-trusted-profile"
  github_repo       = "SocioProphet/prophet-platform"
  cluster_id        = ibm_container_vpc_cluster.this.id
  cos_instance_crn  = var.cos_instance_crn
  state_bucket_name = "prophet-tofu-state-ibm"
}

output "github_ci_trusted_profile_id" {
  value       = module.github_ci.trusted_profile_id
  description = "Set as GitHub Actions variable IBM_TRUSTED_PROFILE_ID (not a secret)."
}
