terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.0" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
  # backend "s3" { ... }  # configure per your state bucket, or run local first
}

provider "aws" {
  region = var.region
}
