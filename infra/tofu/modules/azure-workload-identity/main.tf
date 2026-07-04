# Azure Workload Identity — no static credentials in pods (ADR-050 Azure equivalent).
# AKS workloads assume a User-Assigned Managed Identity via projected OIDC token.
# Requires AKS cluster built with oidc_issuer_enabled = true and
# workload_identity_enabled = true (see azure-aks env).

resource "azurerm_user_assigned_identity" "wi" {
  for_each = var.bindings

  name                = "${var.cluster_name}-${each.key}"
  resource_group_name = var.resource_group
  location            = var.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "wi" {
  for_each = var.bindings

  name                = "${var.cluster_name}-${each.key}"
  resource_group_name = var.resource_group
  parent_id           = azurerm_user_assigned_identity.wi[each.key].id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.oidc_issuer_url
  subject             = "system:serviceaccount:${each.value.k8s_namespace}:${each.value.k8s_sa_name}"
}

resource "azurerm_role_assignment" "wi" {
  for_each = {
    for pair in flatten([
      for slug, cfg in var.bindings : [
        for role in cfg.role_definitions : {
          key   = "${slug}/${role}"
          slug  = slug
          role  = role
          scope = cfg.scope
        }
      ]
    ]) : pair.key => pair
  }

  scope                = each.value.scope
  role_definition_name = each.value.role
  principal_id         = azurerm_user_assigned_identity.wi[each.value.slug].principal_id
}
