# Shared environment — GCP shared projects (logging, monitoring, VPC, platform AR)
# Manages the Shared folder resources only.
# Depends on gcp-landing having been applied first (reads outputs via remote state).

terraform {
  backend "gcs" {
    bucket = "prophet-tofu-state-prod"
    prefix = "shared/terraform.tfstate"
  }
}

provider "google" {}
provider "google-beta" {}

data "terraform_remote_state" "landing" {
  backend = "gcs"
  config = {
    bucket = "prophet-tofu-state-prod"
    prefix = "gcp-landing/terraform.tfstate"
  }
}

locals {
  project_ids = data.terraform_remote_state.landing.outputs.project_ids
  org_id      = data.terraform_remote_state.landing.outputs.org_id
}

# Workload Identity for CI/CD (Tekton + GitHub Actions)
module "wi_cicd" {
  source         = "../../modules/workload-identity"
  project_id     = local.project_ids["platform"]
  project_number = data.terraform_remote_state.landing.outputs.project_ids["platform"]

  bindings = {
    tekton-builder = {
      sa_name       = "tekton-builder"
      k8s_namespace = "tekton-pipelines"
      k8s_sa_name   = "tekton-build-sa"
      roles = [
        "roles/artifactregistry.writer",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectCreator",
      ]
    }
    argocd-deployer = {
      sa_name       = "argocd-deployer"
      k8s_namespace = "argocd"
      k8s_sa_name   = "argocd-application-controller"
      roles = [
        "roles/artifactregistry.reader",
        "roles/container.developer",
      ]
    }
    # Runtime identity for the prod search-orchestrator workload (blue-green Rollout).
    # Minted by tofu so the prod overlay's KSA annotation
    # (iam.gke.io/gcp-service-account: search-orchestrator@…) resolves to a real GSA —
    # one-click deploy, no engineer wires this by hand.
    #
    # roles = [] BY DESIGN (least privilege): the workload calls NO GCP APIs — config is
    # in a ConfigMap, image-pull is the node SA, the PVC is storageclass-provisioned. The
    # identity exists (audit/VPC-SC/future use) but grants nothing. When the app first needs
    # a GCP API, add the SINGLE matching role here (e.g. roles/secretmanager.secretAccessor)
    # — that is the only change, and it stays one-click.
    search-orchestrator = {
      sa_name       = "search-orchestrator"
      k8s_namespace = "prophet-platform-prod"
      k8s_sa_name   = "search-orchestrator"
      roles         = []
    }
  }
}

output "wi_sa_emails" { value = module.wi_cicd.sa_emails }
output "wi_k8s_annotations" { value = module.wi_cicd.k8s_annotation }

# GitHub Actions OIDC federation for GCP drift detection.
# Outputs become GitHub Actions *variables* (not secrets):
#   GCP_WIF_PROVIDER  → module.github_ci_gcp.wif_provider
#   GCP_TOFU_SA       → module.github_ci_gcp.sa_email
module "github_ci_gcp" {
  source            = "../../modules/github-oidc-gcp"
  project_id        = local.project_ids["platform"]
  github_repo       = "SocioProphet/prophet-platform"
  state_bucket_name = "prophet-tofu-state-prod"
}

output "github_ci_wif_provider" {
  value       = module.github_ci_gcp.wif_provider
  description = "Set as GitHub Actions variable GCP_WIF_PROVIDER (not a secret)."
}
output "github_ci_sa_email" {
  value       = module.github_ci_gcp.sa_email
  description = "Set as GitHub Actions variable GCP_TOFU_SA (not a secret)."
}
