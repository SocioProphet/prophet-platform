terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google      = { source = "hashicorp/google", version = "~> 6.0" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 6.0" }
    helm        = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes  = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }

  # First run: comment this out for a local backend, then migrate to GCS.
  backend "gcs" {
    bucket = "prophet-tofu-state-socioprophet"
    prefix = "gcp-gke"
  }
}
