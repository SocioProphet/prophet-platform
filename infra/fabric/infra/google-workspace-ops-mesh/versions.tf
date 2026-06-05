terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }

    googleworkspace = {
      source  = "hashicorp/googleworkspace"
      version = ">= 0.7"
    }

    local = {
      source  = "hashicorp/local"
      version = ">= 2.4"
    }
  }
}
