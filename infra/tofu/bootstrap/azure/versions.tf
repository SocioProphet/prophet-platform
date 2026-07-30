# Version pins for the `bootstrap/azure` root.
#
# Moved out of main.tf so every root under infra/tofu/ declares its versions in
# the same file: envs/*/versions.tf, environments/*/versions.tf, shared/versions.tf.
#
# `required_version` was absent here — see the note in bootstrap/aws/versions.tf.
#
# azurerm moved ~> 3.0 -> ~> 4.0 (3.117.1 -> 4.81.0), matching
# environments/azure-aks, which was already on 4.x. Same class of split as the
# google majors: two azurerm majors in one estate, nothing recording why.
#
# Verified at BOTH majors with OpenTofu 1.8.3, clean init, no plugin cache:
# `tofu validate` returns "Success! The configuration is valid." on 3.117.1 and
# on 4.81.0, no warnings either side. azurerm 4.0 made provider `subscription_id`
# mandatory; this root already sets it from var.subscription_id, which is why the
# move is clean.
#
# ⚠️ Surfaced by the move, NOT fixed here: azurerm_storage_container in main.tf
# sets `storage_account_name`, which 4.x marks deprecated in favour of
# `storage_account_id` and 5.x is expected to remove. Read off the real schema
# (`tofu providers schema -json`, azurerm 4.81.0):
#     storage_account_name -> {"deprecated": true, "optional": true}
#     storage_account_id   -> {"optional": true}
# It still validates clean, so this is a dated obligation rather than a break.
# Swapping the attribute changes which identifier addresses an existing container
# and can produce a diff on a state that already exists — an apply-time question
# this offline-validation PR has no way to answer. Left as a follow-up, stated
# rather than hidden. The deprecation exists in 4.x whether or not this root
# points at it; the bump surfaces it, it does not create it.
#
# Not covered by the evidence above: `tofu plan`/`apply`, which need Azure
# credentials. Schema compatibility across the major is confirmed; apply-time
# behaviour is not.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 4.0" }
  }
}
