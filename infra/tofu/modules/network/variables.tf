variable "host_project_id" { type = string; description = "VPC host project (socioprophet-vpc-host-prod)" }
variable "region"         { type = string; default = "us-central1" }

variable "subnets" {
  type = map(object({
    cidr              = string
    service_project   = optional(string, "")
    secondary_ranges  = optional(map(string), {})
    description       = optional(string, "")
  }))
  default = {
    gke-prod   = { cidr = "10.100.0.0/20", secondary_ranges = { pods = "10.101.0.0/16", services = "10.102.0.0/20" } }
    gke-shared = { cidr = "10.110.0.0/20", secondary_ranges = { pods = "10.111.0.0/16", services = "10.112.0.0/20" } }
  }
}

variable "shared_vpc_service_projects" {
  type    = list(string)
  default = []
  description = "Project IDs to attach as Shared VPC service projects"
}
