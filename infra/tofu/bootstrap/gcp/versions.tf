# Version pins for the `bootstrap/gcp` root.
#
# Moved out of main.tf so every root under infra/tofu/ declares its versions in
# the same file: envs/*/versions.tf, environments/*/versions.tf, shared/versions.tf.
#
# `required_version` was absent here — see the note in bootstrap/aws/versions.tf.
#
# google moved ~> 5.0 -> ~> 6.0 (5.45.2 -> 6.50.0).
#
# The estate was running three google majors at once with nothing recording why:
# bootstrap/gcp on 5.x, environments/gcp-{gke,ephemeral,persistent} on 6.x, and
# envs/* unconstrained and resolving 7.42.0 until #1108 held them at 6.x. Two of
# those three were accidents rather than decisions. 6.x is the estate's majority
# and the one #1108 settled on, so bootstrap follows it: one google major, in one
# place, on purpose.
#
# Verified at BOTH majors with OpenTofu 1.8.3, clean init, no plugin cache:
# `tofu validate` returns "Success! The configuration is valid." on 5.45.2 and on
# 6.50.0, with no warnings either side. This root creates two resources —
# google_storage_bucket and google_storage_bucket_iam_member — both long-stable.
#
# Not covered by that evidence: `tofu plan`/`apply`, which need GCP credentials.
# Schema compatibility across the major is confirmed; apply-time behaviour is not.

terraform {
  required_version = ">= 1.8.0"

  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }

  # Intentional: this bootstrap itself uses a local state file.
  # Once applied, all OTHER envs use the GCS bucket we create here.
}
