variable "env" {
  type        = string
  description = "Environment name (p0-lab, p1-single-site, etc.)"
}

variable "secrets_dir" {
  type        = string
  default     = ""
  description = "Directory where age-encrypted SOPS secret files are written"
}

variable "postgres_password" {
  type      = string
  sensitive = true
}

variable "minio_secret_key" {
  type      = string
  sensitive = true
}

variable "k3s_token" {
  type      = string
  sensitive = true
}
