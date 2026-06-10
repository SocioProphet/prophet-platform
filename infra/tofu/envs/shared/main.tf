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
  }
}

output "wi_sa_emails" { value = module.wi_cicd.sa_emails }
output "wi_k8s_annotations" { value = module.wi_cicd.k8s_annotation }
