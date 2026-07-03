# AWS state bootstrap — run ONCE before any other AWS tofu envs.
# Creates the S3 bucket + DynamoDB lock table used by aws-* backend blocks.
# Uses a local backend here; mirrors infra/terraform/bootstrap/main.tf for the Tofu layer.
# Never destroy without migrating state first.

terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "tofu_state" {
  bucket = var.state_bucket_name

  lifecycle { prevent_destroy = true }

  tags = local.tags
}

resource "aws_s3_bucket_versioning" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "tofu_state" {
  bucket                  = aws_s3_bucket.tofu_state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "tofu_state" {
  bucket = aws_s3_bucket.tofu_state.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
}

resource "aws_dynamodb_table" "tofu_lock" {
  name         = var.lock_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  lifecycle { prevent_destroy = true }

  tags = local.tags
}

locals {
  tags = {
    ManagedBy   = "opentofu"
    Environment = "bootstrap"
    Team        = "platform"
    Repo        = "SocioProphet/prophet-platform"
  }
}

output "state_bucket_arn" {
  value = aws_s3_bucket.tofu_state.arn
}
output "state_bucket_name" {
  value       = aws_s3_bucket.tofu_state.bucket
  description = "Use as bucket = \"...\" in all aws-* backend blocks."
}
output "lock_table_name" {
  value       = aws_dynamodb_table.tofu_lock.name
  description = "Use as dynamodb_table = \"...\" in all aws-* backend blocks."
}
