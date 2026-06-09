# Generates Kubernetes Secret manifests as local files for SOPS/age encryption.
# These are NOT applied directly — they are written to disk, encrypted with SOPS,
# then committed to the GitOps repo. Never commit the plaintext output.

locals {
  out_dir = var.secrets_dir != "" ? var.secrets_dir : "${path.root}/.secrets-staging/${var.env}"
}

resource "local_file" "postgres_secret" {
  filename        = "${local.out_dir}/postgres-credentials.yaml"
  file_permission = "0600"
  content         = <<-YAML
    apiVersion: v1
    kind: Secret
    metadata:
      name: postgres-credentials
      namespace: socioprophet
    type: Opaque
    stringData:
      username: prophet
      password: "${var.postgres_password}"
  YAML
}

resource "local_file" "minio_secret" {
  filename        = "${local.out_dir}/minio-credentials.yaml"
  file_permission = "0600"
  content         = <<-YAML
    apiVersion: v1
    kind: Secret
    metadata:
      name: minio-credentials
      namespace: socioprophet
    type: Opaque
    stringData:
      access-key: prophet
      secret-key: "${var.minio_secret_key}"
  YAML
}

resource "local_file" "k3s_token_secret" {
  filename        = "${local.out_dir}/k3s-token.txt"
  file_permission = "0600"
  content         = var.k3s_token
}
