variable "name" {
  type        = string
  description = "Node name (e.g. prophet-p1-control-0)"
}

variable "server_type" {
  type        = string
  default     = "cpx21"
  description = "Hetzner server type. cpx21 = 3vCPU/4GB. cpx31 = 4vCPU/8GB."
}

variable "location" {
  type        = string
  default     = "ash"
  description = "Hetzner datacenter location (ash=Ashburn, nbg1=Nuremberg, fsn1=Falkenstein)"
}

variable "image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "ssh_public_key_id" {
  type        = string
  description = "Hetzner SSH key resource ID"
}

variable "private_network_id" {
  type        = string
  description = "Hetzner private network ID"
}

variable "private_ip" {
  type        = string
  description = "Fixed private IP for this node within the subnet"
}

variable "firewall_ids" {
  type    = list(string)
  default = []
}

variable "role" {
  type        = string
  default     = "worker"
  description = "Node role: control-plane or worker"
}

variable "k3s_version" {
  type    = string
  default = "v1.30.2+k3s2"
}

variable "k3s_token" {
  type      = string
  sensitive = true
}

variable "k3s_server_url" {
  type        = string
  default     = ""
  description = "URL of control-plane node; empty when this node IS the control-plane"
}

variable "extra_k3s_args" {
  type    = string
  default = ""
}
