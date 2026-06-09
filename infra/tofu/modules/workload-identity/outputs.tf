output "sa_emails" {
  value = { for k, v in google_service_account.wi_sa : k => v.email }
}

output "k8s_annotation" {
  description = "Annotation value to add to each Kubernetes ServiceAccount"
  value = {
    for k, v in google_service_account.wi_sa :
      k => "iam.gke.io/gcp-service-account=${v.email}"
  }
}
