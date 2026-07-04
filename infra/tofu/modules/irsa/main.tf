# IRSA — IAM Roles for Service Accounts (ADR-050 AWS equivalent)
# EKS workloads assume IAM roles via projected OIDC tokens, not static keys.

data "aws_iam_openid_connect_provider" "eks" {
  url = var.oidc_issuer_url
}

resource "aws_iam_role" "irsa" {
  for_each = var.bindings

  name        = "${var.cluster_name}-${each.key}"
  description = "IRSA for ${each.value.k8s_namespace}/${each.value.k8s_sa_name}"
  tags        = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(var.oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:${each.value.k8s_namespace}:${each.value.k8s_sa_name}"
          "${replace(var.oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "irsa" {
  for_each = {
    for pair in flatten([
      for slug, cfg in var.bindings : [
        for arn in cfg.policy_arns : { key = "${slug}/${arn}", slug = slug, arn = arn }
      ]
    ]) : pair.key => pair
  }

  role       = aws_iam_role.irsa[each.value.slug].name
  policy_arn = each.value.arn
}
