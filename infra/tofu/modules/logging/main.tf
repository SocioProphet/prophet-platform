# Centralized logging — routes all project logs to socioprophet-logging-prod
# Immutable audit trail requirement per ADR-050.

variable "logging_project_id" { type = string; description = "socioprophet-logging-prod project ID" }
variable "source_project_ids"  { type = list(string); description = "Projects to aggregate logs from" }
variable "location"            { type = string; default = "us-central1" }
variable "retention_days"      { type = number; default = 365 }

resource "google_logging_project_bucket_config" "audit_bucket" {
  project          = var.logging_project_id
  location         = var.location
  bucket_id        = "prophet-audit-logs"
  retention_days   = var.retention_days
  description      = "Immutable audit log sink — prophet-platform"

  # Prevent accidental deletion of audit evidence
  lifecycle { prevent_destroy = true }
}

resource "google_logging_project_sink" "sinks" {
  for_each               = toset(var.source_project_ids)
  project                = each.value
  name                   = "prophet-audit-sink"
  destination            = "logging.googleapis.com/projects/${var.logging_project_id}/locations/${var.location}/buckets/${google_logging_project_bucket_config.audit_bucket.bucket_id}"
  unique_writer_identity = true

  # Capture all admin activity + data access + system events
  filter = <<-FILTER
    logName=~"cloudaudit.googleapis.com" OR
    logName=~"activity" OR
    severity >= WARNING
  FILTER
}

output "sink_writer_identities" {
  value = { for k, v in google_logging_project_sink.sinks : k => v.writer_identity }
}
