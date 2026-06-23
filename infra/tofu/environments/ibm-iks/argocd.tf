# Argo CD + root app-of-apps — identical to every substrate; only the provider
# auth (IKS admin config) is cloud-specific.
data "ibm_container_cluster_config" "this" {
  cluster_name_id   = ibm_container_vpc_cluster.this.id
  resource_group_id = data.ibm_resource_group.this.id
  admin             = true
}

provider "kubernetes" {
  host                   = data.ibm_container_cluster_config.this.host
  client_certificate     = data.ibm_container_cluster_config.this.admin_certificate
  client_key             = data.ibm_container_cluster_config.this.admin_key
  cluster_ca_certificate = data.ibm_container_cluster_config.this.ca_certificate
}

provider "helm" {
  kubernetes {
    host                   = data.ibm_container_cluster_config.this.host
    client_certificate     = data.ibm_container_cluster_config.this.admin_certificate
    client_key             = data.ibm_container_cluster_config.this.admin_key
    cluster_ca_certificate = data.ibm_container_cluster_config.this.ca_certificate
  }
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = "https://argoproj.github.io/argo-helm"
  chart            = "argo-cd"
  version          = "7.7.7"
  set {
    name  = "crds.keep"
    value = "true"
  }
}

resource "helm_release" "root_app" {
  name       = "root-app"
  namespace  = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argocd-apps"
  version    = "2.0.2"
  depends_on = [helm_release.argocd]

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
        syncPolicy = { automated = { prune = true, selfHeal = true } }
      }
    }
  })]
}
