output "folder_ids" {
  description = "Map of folder slug → folder resource ID (folders/<id>)"
  value       = { for k, v in google_folder.folders : k => v.name }
}
