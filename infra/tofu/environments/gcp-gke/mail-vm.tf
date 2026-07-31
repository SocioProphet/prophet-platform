# Prophet Workspace mail = an edge appliance on a dedicated VM, NOT the Autopilot cluster.
# Mail needs a stable public IP, PTR/reverse-DNS, inbound port 25, and the real client source IP —
# all of which the Autopilot L4 LoadBalancer either mangles or forbids (no hostNetwork/hostPort).
# So SMTP+IMAP live here; the IMAP-client/CalDAV/webmail surfaces stay in-cluster and talk to it over
# standard protocols. Fully IaC'd + PTR set here, so it stays under the same "everything as code" rule.
#
# APPLY ORDERING: this reuses google_compute_address.ws_smtp (currently held by the now-deleted k8s
# workspace-smtp-lb Service). Merge this PR first so ArgoCD prunes the LB and frees the IP, THEN
# `tofu apply` so the VM can claim it. Import the address first (see workspace-mail.tf).

variable "mail_domain" {
  type        = string
  default     = "socioprophet.ai"
  description = "Primary mail domain."
}

variable "network" {
  type        = string
  default     = "default"
  description = "VPC network the mail VM + firewall attach to (match the GKE cluster's network)."
}

locals {
  mail_hostname = "mail.${var.mail_domain}"
  dkim_selector = "default"
  admin_email   = "michael@${var.mail_domain}"
}

# --- Secrets (populate OUT OF BAND so keys never touch tfstate) ---
#   printf %s "$(cat scratchpad/dkim/default.private)" | gcloud secrets versions add mail-dkim-default --data-file=-
#   doveadm pw -s SHA512-CRYPT | gcloud secrets versions add mail-admin-passhash --data-file=-
resource "google_secret_manager_secret" "mail_dkim" {
  secret_id = "mail-dkim-default"
  labels    = local.labels
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "mail_admin_pass" {
  secret_id = "mail-admin-passhash"
  labels    = local.labels
  replication {
    auto {}
  }
}

# --- Least-privilege VM identity: read only its two secrets ---
resource "google_service_account" "mail_vm" {
  account_id   = "mail-vm"
  display_name = "Prophet Workspace mail VM"
}

resource "google_secret_manager_secret_iam_member" "mail_dkim_access" {
  secret_id = google_secret_manager_secret.mail_dkim.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mail_vm.email}"
}

resource "google_secret_manager_secret_iam_member" "mail_admin_pass_access" {
  secret_id = google_secret_manager_secret.mail_admin_pass.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mail_vm.email}"
}

# Persistent data disk — the cert (/etc/letsencrypt), mailboxes (/var/mail), and user db survive
# VM replace/recreate. THE fix for the replace-loop that wiped the cert every iteration and burned
# the Let's Encrypt rate limit. Issue the cert ONCE; it lives here forever (also = the #33 resiliency).
resource "google_compute_disk" "mail_data" {
  name   = "prophet-mail-data"
  type   = "pd-balanced"
  zone   = "${var.region}-a"
  size   = 20
  labels = local.labels
  lifecycle {
    prevent_destroy = true # never let a config change delete mail + certs
  }
}

variable "acme_staging" {
  type        = bool
  default     = true
  description = "true = Let's Encrypt STAGING (untrusted, no rate limit — validate the pipeline). Flip to false for the real cert once prod quota is clear."
}

# --- The mail VM ---
resource "google_compute_instance" "mail" {
  name                      = "prophet-mail"
  machine_type              = "e2-small"
  zone                      = "${var.region}-a"
  tags                      = ["mail"]
  labels                    = local.labels
  allow_stopping_for_update = true

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 30
      type  = "pd-balanced"
    }
  }

  attached_disk {
    source      = google_compute_disk.mail_data.id
    device_name = "maildata"
  }

  network_interface {
    network = var.network
    access_config {
      nat_ip                 = google_compute_address.ws_smtp.address # mail.<domain> (must have the A record + PTR)
      public_ptr_domain_name = "${local.mail_hostname}."              # sets reverse DNS -> mail.<domain>
    }
  }

  service_account {
    email  = google_service_account.mail_vm.email
    scopes = ["cloud-platform"] # narrowed by IAM: SA can only read its two secrets
  }

  metadata_startup_script = templatefile("${path.module}/mail-vm-startup.sh.tftpl", {
    mail_hostname          = local.mail_hostname
    mail_domain            = var.mail_domain
    dkim_selector          = local.dkim_selector
    admin_email            = local.admin_email
    dkim_secret_name       = google_secret_manager_secret.mail_dkim.secret_id
    admin_pass_secret_name = google_secret_manager_secret.mail_admin_pass.secret_id
    acme_staging           = var.acme_staging
  })

  depends_on = [
    google_secret_manager_secret_iam_member.mail_dkim_access,
    google_secret_manager_secret_iam_member.mail_admin_pass_access,
  ]
}

# --- Firewall: mail ports from anywhere (inbound MX + clients), certbot :80, SSH via IAP only ---
resource "google_compute_firewall" "mail_ingress" {
  name          = "mail-ingress"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["mail"]
  allow {
    protocol = "tcp"
    ports    = ["25", "465", "587", "993", "80"] # 80 = certbot HTTP-01
  }
}

resource "google_compute_firewall" "mail_ssh_iap" {
  name          = "mail-ssh-iap"
  network       = var.network
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"] # Google IAP range — no public SSH
  target_tags   = ["mail"]
  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

output "mail_vm_ip" {
  value       = google_compute_instance.mail.network_interface[0].access_config[0].nat_ip
  description = "mail.socioprophet.ai + imap.socioprophet.ai A records point here; PTR set to mail.<domain>."
}

output "mail_vm_name" {
  value = google_compute_instance.mail.name
}
