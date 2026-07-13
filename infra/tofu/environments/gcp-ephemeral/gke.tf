# GKE Autopilot cluster — Google-managed nodes (least ops), Workload Identity on by
# default. Uses the persistent node identity (data.google_service_account.gke_nodes)
# so no SA is created/destroyed on the ephemeral lifecycle. deletion_protection is
# OFF by design: `tofu destroy` must be able to tear this down cleanly.

locals {
  labels = {
    "prophet-platform" = "true"
    "managed-by"       = "opentofu"
    "source-of-truth"  = "git"
    "org"              = "socioprophet"
    "lifecycle"        = "ephemeral"
  }
}

resource "google_container_cluster" "this" {
  name                = var.cluster_name
  location            = var.region
  enable_autopilot    = true
  deletion_protection = false

  release_channel { channel = "REGULAR" }

  # Autopilot node identity (the long-lived SA from the persistent stack).
  cluster_autoscaling {
    auto_provisioning_defaults {
      service_account = data.google_service_account.gke_nodes.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }

  resource_labels = local.labels
}
