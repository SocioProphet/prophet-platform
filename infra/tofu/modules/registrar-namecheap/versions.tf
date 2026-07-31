terraform {
  required_version = ">= 1.8.0"

  required_providers {
    namecheap = {
      source  = "namecheap/namecheap"
      version = "~> 2.1"
    }
  }
}
