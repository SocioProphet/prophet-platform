variable "org_id"         { type = string }
variable "billing_account" { type = string }

variable "projects" {
  type = map(object({
    project_id   = string
    display_name = string
    folder_key   = string             # slug from modules/folders
    folder_ids   = map(string)        # pass the full folder_ids output here
    services     = optional(list(string), [])
    labels       = optional(map(string), {})
  }))
  description = "Map of project definitions. Key is a stable slug."
}
