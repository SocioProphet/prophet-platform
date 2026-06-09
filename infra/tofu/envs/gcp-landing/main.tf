# GCP Landing Zone — socioprophet.ai org
#
# APPLY GATE: plan-only in CI. No apply without:
#   1. Manual approval in GitHub Actions environment "gcp-prod"
#   2. Signed plan artifact (SLSA provenance)
#   3. Destroy review documented in ADR or GitHub issue
#
# This env creates the org-level shape only.
# Per-project workloads are deployed by Argo CD from Kustomize manifests.

terraform {
  backend "gcs" {
    bucket = "prophet-tofu-state-prod"
    prefix = "gcp-landing/terraform.tfstate"
  }
}

provider "google" {
  # Credentials via Workload Identity Federation in CI;
  # gcloud application-default credentials locally.
  # Never commit a service account key.
}

provider "google-beta" {}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "org_domain"        { type = string; default = "socioprophet.ai" }
variable "billing_account"   { type = string }
variable "admin_group_email" { type = string; default = "platform-admins@socioprophet.ai" }
variable "alert_email"       { type = string; default = "ops@socioprophet.ai" }

# ── Org ───────────────────────────────────────────────────────────────────────

module "org" {
  source            = "../../modules/org"
  org_domain        = var.org_domain
  billing_account   = var.billing_account
  admin_group_email = var.admin_group_email
}

# ── Folders ───────────────────────────────────────────────────────────────────

module "folders" {
  source = "../../modules/folders"
  org_id = module.org.org_id
  folders = {
    production = { display_name = "Production" }
    shared     = { display_name = "Shared" }
  }
}

# ── Projects ──────────────────────────────────────────────────────────────────

module "projects" {
  source          = "../../modules/projects"
  org_id          = module.org.org_id
  billing_account = var.billing_account

  projects = {
    platform = {
      project_id   = "socioprophet-platform"
      display_name = "Prophet Platform"
      folder_key   = "shared"
      folder_ids   = module.folders.folder_ids
      services = [
        "artifactregistry.googleapis.com",
        "container.googleapis.com",
        "secretmanager.googleapis.com",
        "cloudkms.googleapis.com",
        "iam.googleapis.com",
      ]
    }
    logging = {
      project_id   = "socioprophet-logging-prod"
      display_name = "Prophet Logging Prod"
      folder_key   = "shared"
      folder_ids   = module.folders.folder_ids
      services     = ["logging.googleapis.com", "bigquery.googleapis.com"]
    }
    monitoring = {
      project_id   = "socioprophet-monitoring-prod"
      display_name = "Prophet Monitoring Prod"
      folder_key   = "shared"
      folder_ids   = module.folders.folder_ids
      services     = ["monitoring.googleapis.com", "cloudtrace.googleapis.com"]
    }
    vpc_host = {
      project_id   = "socioprophet-vpc-host-prod"
      display_name = "Prophet VPC Host Prod"
      folder_key   = "shared"
      folder_ids   = module.folders.folder_ids
      services     = ["compute.googleapis.com", "container.googleapis.com"]
    }
    web = {
      project_id   = "socioprophet-web"
      display_name = "SocioProphet Web"
      folder_key   = "production"
      folder_ids   = module.folders.folder_ids
      services     = ["run.googleapis.com", "firebase.googleapis.com"]
    }
    cloud = {
      project_id   = "socioprophet-cloud"
      display_name = "SocioProphet Cloud"
      folder_key   = "production"
      folder_ids   = module.folders.folder_ids
      services     = ["container.googleapis.com", "compute.googleapis.com"]
    }
    im = {
      project_id   = "socioprophet-im"
      display_name = "SocioProphet IM"
      folder_key   = "production"
      folder_ids   = module.folders.folder_ids
      services     = ["container.googleapis.com"]
    }
    social = {
      project_id   = "socioprophet-social"
      display_name = "SocioProphet Social"
      folder_key   = "production"
      folder_ids   = module.folders.folder_ids
      services     = ["container.googleapis.com"]
    }
    news = {
      project_id   = "socioprophet-news"
      display_name = "SocioProphet News"
      folder_key   = "production"
      folder_ids   = module.folders.folder_ids
      services     = ["container.googleapis.com"]
    }
  }
}

# ── Network (Shared VPC) ──────────────────────────────────────────────────────

module "network" {
  source          = "../../modules/network"
  host_project_id = module.projects.project_ids["vpc_host"]
  shared_vpc_service_projects = [
    module.projects.project_ids["cloud"],
    module.projects.project_ids["im"],
    module.projects.project_ids["social"],
    module.projects.project_ids["news"],
  ]
}

# ── Artifact Registry (platform project, us-central1) ────────────────────────

module "artifact_registry" {
  source     = "../../modules/artifact-registry"
  project_id = module.projects.project_ids["platform"]
  location   = "us-central1"
  repositories = {
    core   = { description = "Core platform services" }
    web    = { description = "Web surface" }
    edge   = { description = "Edge and fog services" }
    social = { description = "Social surface" }
    im     = { description = "IM/messaging surface" }
    news   = { description = "News surface" }
  }
}

# ── Policy ────────────────────────────────────────────────────────────────────

module "policy" {
  source     = "../../modules/policy"
  org_id     = module.org.org_id
  folder_ids = module.folders.folder_ids
}

# ── Logging ───────────────────────────────────────────────────────────────────

module "logging" {
  source             = "../../modules/logging"
  logging_project_id = module.projects.project_ids["logging"]
  source_project_ids = values(module.projects.project_ids)
}

# ── Monitoring ────────────────────────────────────────────────────────────────

module "monitoring" {
  source                = "../../modules/monitoring"
  monitoring_project_id = module.projects.project_ids["monitoring"]
  scoped_project_ids    = values(module.projects.project_ids)
  alert_email           = var.alert_email
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "org_id"           { value = module.org.org_id }
output "folder_ids"       { value = module.folders.folder_ids }
output "project_ids"      { value = module.projects.project_ids }
output "registry_urls"    { value = module.artifact_registry.repository_urls }
output "vpc_id"           { value = module.network.vpc_id }
