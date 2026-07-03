output "mesh_summary" {
  description = "Non-secret summary of the prepared deployment mesh."
  value       = local.mesh_summary
}

output "generated_dir" {
  description = "Absolute path where generated local deployment files are written."
  value       = local.generated_dir
}

output "apps_script_config_preview" {
  description = "Generated Apps Script config preview. Contains IDs but no secrets."
  value       = local.apps_script_config
  sensitive   = false
}

output "workspace_group_keys" {
  description = "Workspace group keys prepared for optional management."
  value       = keys(var.workspace_groups)
}
