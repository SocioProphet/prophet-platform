terraform {
  required_version = ">= 1.6.0"

  required_providers {
    googleworkspace = {
      source  = "hashicorp/googleworkspace"
      version = ">= 0.7"
    }
  }
}
