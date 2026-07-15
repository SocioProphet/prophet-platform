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

  # ArgoCD 2.13.1's bundled OpenAPI schema predates Kubernetes 1.35's
  # Deployment.status.terminatingReplicas field, so its structured-merge (server-side-apply)
  # diff fails to build a typed value from live Deployments — "field not declared in schema" —
  # and silently stops syncing every app with a Deployment. Ignoring the (non-desired-state)
  # .status field on all resources sidesteps it cluster-wide. Proper long-term fix: upgrade
  # ArgoCD to a build whose schema knows this field (tracked separately).
  values = [yamlencode({
    configs = {
      cm = {
        "resource.compareoptions" = "ignoreResourceStatusField: all\n"
      }
    }
  })]
}

# Root app-of-apps: Argo watches deploy/argocd and applies the ApplicationSets
# (platform-services, workspace-services, fogstack) found there. Created via the
# argocd-apps Helm chart through the configured provider — no kubectl/kubeconfig
# dependency, and it applies after Argo's CRDs exist (depends_on).
resource "helm_release" "root_app" {
  name       = "root-app"
  namespace  = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.2"
  depends_on = [helm_release.argocd]

  # argocd-apps expects `applications` as a MAP keyed by name (not a list).
  values = [yamlencode({
    applications = {
      root = {
        namespace = "argocd"
        project   = "default"
        source = {
          repoURL        = var.gitops_repo_url
          targetRevision = var.gitops_revision
          path           = var.gitops_path
          directory      = { recurse = true }
        }
        destination = {
          server    = "https://kubernetes.default.svc"
          namespace = "argocd"
        }
        syncPolicy = {
          automated = { prune = true, selfHeal = true }
        }
      }
    }
  })]
}
