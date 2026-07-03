output "workspace_group_keys" {
  description = "Workspace group keys managed by this optional root."
  value       = keys(var.workspace_groups)
}

output "workspace_group_emails" {
  description = "Workspace group email labels managed by this optional root."
  value       = [for group in var.workspace_groups : group.email]
}
