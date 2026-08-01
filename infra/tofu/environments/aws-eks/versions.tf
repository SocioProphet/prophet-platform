terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.0" }
    helm       = { source = "hashicorp/helm", version = "~> 2.13" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.30" }

    # Pulled in transitively by terraform-aws-modules/{vpc,eks}, which constrain
    # them with a floor and no ceiling: tls >= 3.0.0, time >= 0.9.0,
    # cloudinit >= 2.0.0, null >= 3.0.0. A floor-only constraint is not a pin —
    # tls was resolving 4.3.0, a full major above its stated minimum, and would
    # have crossed into 5.x unannounced the day it shipped. Declaring them here
    # adds the missing ceiling; the committed lock then fixes the exact build.
    # tls and null match the constraints already written in shared/versions.tf.
    cloudinit = { source = "hashicorp/cloudinit", version = "~> 2.4" }
    null      = { source = "hashicorp/null", version = "~> 3.2" }
    time      = { source = "hashicorp/time", version = "~> 0.14" }
    tls       = { source = "hashicorp/tls", version = "~> 4.0" }
  }
  # backend "s3" { ... }  # configure per your state bucket, or run local first
}

provider "aws" {
  region = var.region
}
