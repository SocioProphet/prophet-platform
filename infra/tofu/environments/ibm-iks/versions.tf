terraform {
  required_version = ">= 1.8.0"
  required_providers {
    ibm        = { source = "IBM-Cloud/ibm", version = "~> 1.70" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
}

provider "ibm" {
  region = var.region # needs IC_API_KEY in the environment
}
