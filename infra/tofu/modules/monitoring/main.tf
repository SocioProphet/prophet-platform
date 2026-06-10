# Centralized monitoring workspace — socioprophet-monitoring-prod
variable "monitoring_project_id" {
  type        = string
  description = "socioprophet-monitoring-prod project ID"
}
variable "scoped_project_ids" {
  type        = list(string)
  description = "Projects to pull metrics from"
}
variable "alert_email" {
  type = string
}
variable "alert_pagerduty_key" {
  type      = string
  default   = ""
  sensitive = true
}

resource "google_monitoring_monitored_project" "scoped" {
  for_each      = toset(var.scoped_project_ids)
  metrics_scope = "locations/global/metricsScopes/${var.monitoring_project_id}"
  name          = each.value
}

resource "google_monitoring_notification_channel" "email" {
  project      = var.monitoring_project_id
  display_name = "Prophet Platform Alerts (email)"
  type         = "email"
  labels       = { email_address = var.alert_email }
}

resource "google_monitoring_notification_channel" "pagerduty" {
  count        = var.alert_pagerduty_key != "" ? 1 : 0
  project      = var.monitoring_project_id
  display_name = "Prophet Platform Alerts (PagerDuty)"
  type         = "pagerduty"
  sensitive_labels { service_key = var.alert_pagerduty_key }
}

output "notification_channel_ids" {
  value = compact([
    google_monitoring_notification_channel.email.id,
    length(google_monitoring_notification_channel.pagerduty) > 0
    ? google_monitoring_notification_channel.pagerduty[0].id
    : ""
  ])
}
