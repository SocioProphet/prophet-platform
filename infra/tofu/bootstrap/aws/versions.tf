# Version pins for the `bootstrap/aws` root.
#
# Moved out of main.tf so every root under infra/tofu/ declares its versions in
# the same file: envs/*/versions.tf, environments/*/versions.tf, shared/versions.tf.
#
# `required_version` was absent here. It was set on all six environments/* roots
# and, since #1108, on all four envs/* roots — bootstrap/* was the only tier
# without it, so these three were the only roots an older OpenTofu would happily
# parse. >= 1.8.0 matches every other root and the TOFU_VERSION (1.8.3) in
# .github/workflows/tofu-plan.yml.
#
# aws stays at 5.x, matching environments/aws-eks. One aws major in the estate.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}
