variable "project_id" {
  type = string
}
variable "location" {
  type    = string
  default = "us-central1"
}

variable "repositories" {
  type = map(object({
    description = optional(string, "")
    format      = optional(string, "DOCKER")
    # Immutable image policy — requires digest-pinned tags (ADR-040)
    immutable_tags = optional(bool, false)
  }))
  description = "Map of repo slug → config. Slugs: core, web, edge, social, im, news"
  default = {
    core   = { description = "Core platform services" }
    web    = { description = "Web surface" }
    edge   = { description = "Edge and fog services" }
    social = { description = "Social surface" }
    im     = { description = "IM/messaging surface" }
    news   = { description = "News surface" }
  }
}

variable "reader_service_accounts" {
  type        = list(string)
  default     = []
  description = "SAs granted roles/artifactregistry.reader on all repos"
}
