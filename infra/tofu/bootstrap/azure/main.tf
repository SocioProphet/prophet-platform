# Azure state bootstrap — run once before any other Azure tofu envs.
# Creates the Storage Account + container that backs the azurerm backend.
# Never destroy without migrating state first.

terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

resource "azurerm_resource_group" "state" {
  name     = "prophet-tofu-state-rg"
  location = var.location
  tags     = local.tags

  lifecycle { prevent_destroy = true }
}

resource "azurerm_storage_account" "state" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.state.name
  location                 = azurerm_resource_group.state.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
    delete_retention_policy { days = 90 }
  }

  tags = local.tags

  lifecycle { prevent_destroy = true }
}

resource "azurerm_storage_container" "state" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.state.name
  container_access_type = "private"

  lifecycle { prevent_destroy = true }
}

locals {
  tags = {
    managed-by  = "opentofu"
    environment = "bootstrap"
    team        = "platform"
    repo        = "SocioProphet/prophet-platform"
  }
}

output "storage_account_name" {
  value       = azurerm_storage_account.state.name
  description = "Set as backend storage_account_name in azure-aks/versions.tf."
}
output "container_name" {
  value       = azurerm_storage_container.state.name
  description = "Set as backend container_name in azure-aks/versions.tf."
}
output "resource_group_name" {
  value       = azurerm_resource_group.state.name
  description = "Set as backend resource_group_name in azure-aks/versions.tf."
}
