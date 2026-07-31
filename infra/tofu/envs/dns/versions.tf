terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    namecheap = {
      source  = "namecheap/namecheap"
      version = "~> 2.1"
    }
  }

  # First run: comment this out for a local backend, then migrate to GCS.
  # prefix is a directory-like prefix (GCS appends the state object under it).
  backend "gcs" {
    bucket = "prophet-tofu-state-prod"
    prefix = "dns"
  }
}
