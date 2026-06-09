# Prod environment — production project workloads
# Depends on gcp-landing + shared having been applied.

terraform {
  backend "gcs" {
    bucket = "prophet-tofu-state-prod"
    prefix = "prod/terraform.tfstate"
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

data "terraform_remote_state" "shared" {
  backend = "gcs"
  config = {
    bucket = "prophet-tofu-state-prod"
    prefix = "shared/terraform.tfstate"
  }
}

locals {
  project_ids = data.terraform_remote_state.landing.outputs.project_ids
  wi_emails   = data.terraform_remote_state.shared.outputs.wi_sa_emails
}

# Production secrets (shells only — values populated out-of-band)
module "prod_secrets" {
  source     = "../../modules/secrets"
  project_id = local.project_ids["cloud"]

  secrets = {
    postgres-password    = { accessor_sas = [local.wi_emails["tekton-builder"]] }
    minio-secret-key     = { accessor_sas = [local.wi_emails["tekton-builder"]] }
    dovecot-ldap-bind    = { accessor_sas = [] }
    smtp-dkim-key        = { accessor_sas = [] }
  }
}

# Production IAM — persona model per ADR-050
module "prod_iam" {
  source     = "../../modules/iam"
  project_id = local.project_ids["cloud"]

  bindings = {
    deployer = {
      role    = "roles/container.developer"
      members = ["serviceAccount:${local.wi_emails["argocd-deployer"]}"]
    }
    log-writer = {
      role    = "roles/logging.logWriter"
      members = ["serviceAccount:${local.wi_emails["tekton-builder"]}"]
    }
  }
}

output "secret_ids" { value = module.prod_secrets.secret_ids }
