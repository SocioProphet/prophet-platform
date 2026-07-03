terraform {
  required_version = ">= 1.8.0"
  required_providers {
    ibm        = { source = "IBM-Cloud/ibm", version = "~> 1.70" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }
  }
  # IBM COS is S3-compatible — use the S3 backend with profile-based auth.
  # Run `ibmcloud iam oauth-tokens` and set IBM_HMAC_ACCESS_KEY_ID +
  # IBM_HMAC_SECRET_ACCESS_KEY in CI from the Trusted Profile session token.
  backend "s3" {
    bucket                      = "prophet-tofu-state-ibm"
    key                         = "ibm-iks/terraform.tfstate"
    region                      = "us-south"
    endpoint                    = "https://s3.us-south.cloud-object-storage.appdomain.cloud"
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_requesting_account_id  = true
  }
}

provider "ibm" {
  region = var.region # CI: IBM_TRUSTED_PROFILE_ID + short-lived OIDC token via github-oidc; no static API keys
}
