# Cross-stack references to the PERSISTENT foundation (decoupled — looked up by
# name, no remote-state coupling). The node SA and registry are created once in
# gcp-persistent and reused by every ephemeral cluster.

data "google_service_account" "gke_nodes" {
  account_id = var.node_sa_account_id
}

# Cluster auth token for the kubernetes/helm providers.
data "google_client_config" "default" {}
