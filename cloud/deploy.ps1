# PowerShell-safe deployment script (run from repo root or cloud/)

param(
  [string]$Project = "throwpro",
  [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"

Write-Host "Enabling required APIs..."
gcloud services enable storage.googleapis.com pubsub.googleapis.com run.googleapis.com cloudfunctions.googleapis.com firestore.googleapis.com --project $Project | Out-Null

Write-Host "Deploying Cloud Function (ingest_blur)..."
gcloud functions deploy ingest-blur `
  --gen2 `
  --region $Region `
  --project $Project `
  --runtime python311 `
  --entry-point gcs_entrypoint `
  --trigger-bucket praxisforma-videos `
  --service-account throwpro-function-sa@$Project.iam.gserviceaccount.com `
  --source ..\backend\gcp\ingest_blur `
  --set-env-vars GCP_PROJECT=$Project,GCS_BUCKET=praxisforma-videos,PUBSUB_TOPIC=throwpro-analyze

Write-Host "Building & Deploying Cloud Run worker..."
pushd ..\backend
gcloud run deploy throwpro-worker `
  --project $Project `
  --region $Region `
  --source . `
  --allow-unauthenticated `
  --service-account throwpro-worker-sa@$Project.iam.gserviceaccount.com `
  --set-env-vars GCP_PROJECT=$Project,GCS_BUCKET=praxisforma-videos,FIRESTORE_COLLECTION=throwSessions
$WORKER_URL = (gcloud run services describe throwpro-worker --project $Project --region $Region --format "value(status.url)")
popd

Write-Host "Creating Pub/Sub topic and push subscription..."
gcloud pubsub topics create throwpro-analyze --project $Project 2>$null | Out-Null
gcloud pubsub subscriptions create throwpro-analyze-push `
  --project $Project `
  --topic throwpro-analyze `
  --push-endpoint "$WORKER_URL/pubsub" `
  --push-auth-service-account throwpro-worker-sa@$Project.iam.gserviceaccount.com 2>$null | Out-Null

Write-Host "Deployment complete. Worker URL: $WORKER_URL"
Write-Host "If Firestore not enabled, initialize in Native mode via Console."

Write-Host "Smoke test commands:"
Write-Host "- Upload a sample: gsutil cp sample.mp4 gs://praxisforma-videos/incoming/demo-user/sample.mp4"
Write-Host "- Check logs: gcloud functions logs read ingest-blur --gen2 --region $Region --project $Project"
Write-Host "- Check worker logs: gcloud run services logs read throwpro-worker --region $Region --project $Project"


