variable "project_id" {
  type    = string
  default = "socioprophet-platform"
}

variable "region" {
  type    = string
  default = "us-central1"
}

# Zonal disks pin their consumer pod to this zone (Autopilot honors the PV topology).
variable "zone" {
  type    = string
  default = "us-central1-a"
}

# CI push identity (the build-image workflow) — granted writer on the registry.
variable "ci_service_account" {
  type    = string
  default = "sourceos-ci@socioprophet-platform.iam.gserviceaccount.com"
}

# Retained data disks (GB, pd-balanced). Sized for a demo; grow later without recreate.
variable "hellgraph_disk_gb" {
  type    = number
  default = 50
}

variable "postgres_disk_gb" {
  type    = number
  default = 50
}
