terraform {
  required_version = ">= 1.8.0"

  required_providers {
    # GCP — used only in envs/gcp-* and modules that explicitly declare provider
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    # Provider-agnostic
    local  = { source = "hashicorp/local",  version = "~> 2.5" }
    null   = { source = "hashicorp/null",   version = "~> 3.2" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
    tls    = { source = "hashicorp/tls",    version = "~> 4.0" }
  }
}
