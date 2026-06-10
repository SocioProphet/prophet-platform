variable "org_id" {
  type        = string
  description = "GCP organization ID (numeric)"
}

variable "folders" {
  type = map(object({
    display_name = string
    parent       = optional(string, "") # empty = org root; otherwise a folder ID or key from this map
  }))
  description = "Folder definitions. Key is a stable slug used for cross-referencing."
  default = {
    production = { display_name = "Production" }
    shared     = { display_name = "Shared" }
  }
}
