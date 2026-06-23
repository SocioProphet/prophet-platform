# Argo CD on the cluster + the root "app of apps" that points Argo at the
# gitops repo's deploy/argocd directory (where the ApplicationSets live).

provider "kubernetes" {
  host                   = "https://${google_container_cluster.this.endpoint}"
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(google_container_cluster.this.master_auth[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = "https://${google_container_cluster.this.endpoint}"
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(google_container_cluster.this.master_auth[0].cluster_ca_certificate)
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "7.7.7"

  # Keep CRDs; let Argo self-manage after bootstrap.
  set {
    name  = "crds.keep"
    value = "true"
  }
}

# Root app-of-apps: Argo watches deploy/argocd and applies the ApplicationSets
# (platform-services, workspace-services, fogstack) found there. Applied via
# kubectl after the CRDs exist (avoids kubernetes_manifest plan-time CRD races).
resource "null_resource" "root_app" {
  depends_on = [helm_release.argocd]

  triggers = {
    repo     = var.gitops_repo_url
    revision = var.gitops_revision
    path     = var.gitops_path
  }

  provisioner "local-exec" {
    command = <<-EOT
      cat <<'YAML' | kubectl apply -f -
      apiVersion: argoproj.io/v1alpha1
      kind: Application
      metadata:
        name: root
        namespace: argocd
      spec:
        project: default
        source:
          repoURL: ${var.gitops_repo_url}
          targetRevision: ${var.gitops_revision}
          path: ${var.gitops_path}
          directory: { recurse: true }
        destination:
          server: https://kubernetes.default.svc
          namespace: argocd
        syncPolicy:
          automated: { prune: true, selfHeal: true }
      YAML
    EOT
  }
}
