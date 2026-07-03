# GitHub Actions OIDC federation for AWS — no static credentials in CI.
# Creates the IAM OIDC identity provider for token.actions.githubusercontent.com
# and an IAM role that GitHub Actions workflows can assume via AssumeRoleWithWebIdentity.
#
# Usage: after apply, store the role_arn output as a GitHub Actions variable
# (not a secret — it is not a credential).

data "aws_caller_identity" "current" {}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
  tags            = var.tags
}

resource "aws_iam_role" "github_ci" {
  name        = "${var.role_name_prefix}-github-ci"
  description = "Assumed by GitHub Actions for ${var.github_repo} via OIDC — no static keys"
  tags        = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
        }
        StringEquals = {
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_ci_state" {
  name = "tofu-state-access"
  role = aws_iam_role.github_ci.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.state_bucket_name}",
          "arn:aws:s3:::${var.state_bucket_name}/*",
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"]
        Resource = "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/${var.lock_table_name}"
      },
    ]
  })
}

# Read-only plan access for drift detection on EKS/VPC/IAM/ECR.
resource "aws_iam_role_policy_attachment" "github_ci_read" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy",
    "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess",
    "arn:aws:iam::aws:policy/AmazonECR_ReadOnlyAccess_Policy",
    "arn:aws:iam::aws:policy/IAMReadOnlyAccess",
  ])
  role       = aws_iam_role.github_ci.name
  policy_arn = each.key
}
