# AWS EKS substrate. Same platform, AWS underneath: EKS cluster (system +
# scale-to-zero GPU node group) + ECR. App layer (charts/ + deploy/argocd) is
# unchanged. Uses the upstream vpc + eks modules.

data "aws_availability_zones" "available" {
  state = "available"
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name            = var.cluster_name
  cidr            = "10.0.0.0/16"
  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
  tags               = local.prophet_tags
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name                             = var.cluster_name
  cluster_version                          = "1.30"
  cluster_endpoint_public_access           = true
  enable_cluster_creator_admin_permissions = true
  # Enable OIDC provider so IRSA can federate pod identity (no static AWS keys).
  enable_irsa = true
  tags        = local.prophet_tags

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    system = {
      instance_types = ["t3.large"]
      min_size       = 2
      max_size       = 3
      desired_size   = 2
    }
    # GPU pool for finetuning / model training; scales 0→N on demand.
    gpu = {
      instance_types = ["g4dn.xlarge"]
      min_size       = 0
      max_size       = var.gpu_max_nodes
      desired_size   = 0
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "present"
          effect = "NO_SCHEDULE"
        }
      }
    }
  }
}

locals {
  prophet_tags = {
    "prophet.ai/managed-by" = "opentofu"
    "prophet.ai/env"        = var.cluster_name
    "org"                   = "socioprophet"
    "source-of-truth"       = "git"
  }
}

# IRSA — no static AWS credentials in pods (mirrors GCP Workload Identity)
module "irsa" {
  source          = "../../modules/irsa"
  cluster_name    = var.cluster_name
  oidc_issuer_url = module.eks.cluster_oidc_issuer_url
  tags            = local.prophet_tags

  bindings = {
    argocd-deployer = {
      k8s_namespace = "argocd"
      k8s_sa_name   = "argocd-server"
      policy_arns   = ["arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"]
    }
    tekton-builder = {
      k8s_namespace = "tekton-pipelines"
      k8s_sa_name   = "tekton-builder"
      policy_arns = [
        "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser",
        "arn:aws:iam::aws:policy/SecretsManagerReadWrite",
      ]
    }
  }
}

# GitHub Actions OIDC — CI gets a federated IAM role, no static credentials
module "github_ci" {
  source            = "../../modules/github-oidc-aws"
  github_repo       = "SocioProphet/prophet-platform"
  state_bucket_name = "prophet-terraform-state"
  lock_table_name   = "prophet-terraform-locks"
  tags              = local.prophet_tags
}

# Container registry (the ECR equivalent of GAR).
resource "aws_ecr_repository" "images" {
  name         = "socioprophet"
  force_delete = true
  tags         = local.prophet_tags
  image_scanning_configuration {
    scan_on_push = true
  }
}
