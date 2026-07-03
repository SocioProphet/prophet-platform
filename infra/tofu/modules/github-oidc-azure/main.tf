# GitHub Actions OIDC federation for Azure — no static credentials in CI.
# Creates a User-Assigned Managed Identity for GitHub Actions and wires
# Federated Identity Credentials for the main branch and PR/environment workflows.

resource "azurerm_user_assigned_identity" "github_ci" {
  name                = "${var.cluster_name}-github-ci"
  resource_group_name = var.resource_group
  location            = var.location
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "main_branch" {
  name                = "${var.cluster_name}-github-ci-main"
  resource_group_name = var.resource_group
  parent_id           = azurerm_user_assigned_identity.github_ci.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:ref:refs/heads/main"
}

resource "azurerm_federated_identity_credential" "pr" {
  name                = "${var.cluster_name}-github-ci-pr"
  resource_group_name = var.resource_group
  parent_id           = azurerm_user_assigned_identity.github_ci.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repo}:pull_request"
}

# Read-only access for drift detection plan.
resource "azurerm_role_assignment" "github_ci_reader" {
  scope                = var.subscription_scope
  role_definition_name = "Reader"
  principal_id         = azurerm_user_assigned_identity.github_ci.principal_id
}

resource "azurerm_role_assignment" "github_ci_aks_viewer" {
  scope                = var.cluster_scope
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = azurerm_user_assigned_identity.github_ci.principal_id
}
