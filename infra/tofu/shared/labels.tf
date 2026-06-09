# Canonical resource labels applied to every provisioned resource.
# Provider-agnostic: callers map these to GCP labels, AWS tags, etc.
locals {
  prophet_labels = {
    "prophet-platform"   = "true"
    "managed-by"         = "opentofu"
    "source-of-truth"    = "git"
    "org"                = "socioprophet"
  }
}
