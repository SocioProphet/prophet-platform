output "project_ids" {
  description = "Map of project slug → project_id string"
  value       = { for k, v in google_project.projects : k => v.project_id }
}

output "project_numbers" {
  description = "Map of project slug → project number (used for WI, SA refs)"
  value       = { for k, v in google_project.projects : k => v.number }
}
