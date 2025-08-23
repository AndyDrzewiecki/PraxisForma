terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

variable "project" {}
variable "region" { default = "us-central1" }
variable "worker_url" { description = "Cloud Run worker URL for push subscription" }

resource "google_pubsub_topic" "analyze" {
  name = "throwpro-analyze"
}

resource "google_service_account" "function_sa" {
  account_id   = "throwpro-function-sa"
  display_name = "ThrowPro Cloud Function SA"
}

resource "google_service_account" "worker_sa" {
  account_id   = "throwpro-worker-sa"
  display_name = "ThrowPro Cloud Run Worker SA"
}

resource "google_project_iam_member" "function_storage" {
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "function_pubsub_pub" {
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "worker_storage" {
  role   = "roles/storage.admin"
  member = "serviceAccount:${google_service_account.worker_sa.email}"
}

resource "google_project_iam_member" "worker_firestore" {
  role   = "roles/datastore.user"
  member = "serviceAccount:${google_service_account.worker_sa.email}"
}

resource "google_pubsub_subscription" "analyze_push" {
  name  = "throwpro-analyze-push"
  topic = google_pubsub_topic.analyze.name

  push_config {
    push_endpoint = var.worker_url
    oidc_token {
      service_account_email = google_service_account.worker_sa.email
    }
  }
}

output "topic_name" {
  value = google_pubsub_topic.analyze.name
}

output "notes" {
  value = "Initialize Firestore in Native mode manually if not enabled. Update worker_url after deploy."
}


