# Bootstrap — provision the S3 bucket + DynamoDB table that back Terraform state
# for the p1-single-site environment.
#
# Apply this ONCE before running any other terraform env in this repo:
#   terraform init -backend=false && terraform apply
#
# After apply, the bucket ARN is in the outputs — paste it into
# infra/terraform/environments/*/main.tf backend "s3" blocks.

terraform {
  required_version = ">= 1.7.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  # Intentionally no remote backend — this is the bootstrap that creates the backend.
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "bucket_name" {
  type    = string
  default = "prophet-terraform-state"
}

variable "lock_table_name" {
  type    = string
  default = "prophet-terraform-locks"
}

locals {
  common_tags = {
    "prophet.ai/managed-by" = "terraform"
    "prophet.ai/env"        = "bootstrap"
    "org"                   = "socioprophet"
  }
}

resource "aws_s3_bucket" "state" {
  bucket = var.bucket_name
  tags   = local.common_tags

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_dynamodb_table" "state_lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  tags         = local.common_tags

  attribute {
    name = "LockID"
    type = "S"
  }

  lifecycle {
    prevent_destroy = true
  }
}

output "state_bucket_arn" { value = aws_s3_bucket.state.arn }
output "state_bucket_name" { value = aws_s3_bucket.state.bucket }
output "lock_table_name" { value = aws_dynamodb_table.state_lock.name }
