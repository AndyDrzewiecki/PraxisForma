#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
REGION=${REGION:-us-central1}
SERVICE=${SERVICE:-throwpro-api}
SOURCE_DIR=${SOURCE_DIR:-throwpro/backend}
BUCKET=${BUCKET:-$PROJECT_ID-assets}
ORIGINS=${ORIGINS:-http://localhost:5173}

if [[ -z "$PROJECT_ID" ]]; then
  echo "Set PROJECT_ID env var or gcloud config project"
  exit 1
fi

gcloud artifacts repositories describe cloud-run-source-deploy --location=$REGION >/dev/null 2>&1 || \
gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location=$REGION --description="Cloud Run source builds"

CB_SA="$(gcloud projects get-iam-policy $PROJECT_ID --flatten='bindings[].members' --filter='bindings.role:roles/cloudbuild.builds.builder' --format='value(bindings.members)' | head -n1)"
CR_SA="service-$((gcloud projects describe $PROJECT_ID --format='value(projectNumber)'))@serverless-robot-prod.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT_ID --member="$CB_SA" --role=roles/artifactregistry.writer || true
gcloud projects add-iam-policy-binding $PROJECT_ID --member="$CR_SA" --role=roles/run.admin || true

gcloud run deploy "$SERVICE" \
  --source="$SOURCE_DIR" \
  --region="$REGION" \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET=$BUCKET,CORS_ORIGINS=$ORIGINS,ENVELOPES_USE_GCS=true

echo "Deployed $SERVICE in $REGION"

URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')
echo "Service URL: $URL"
curl -sf "$URL/healthz" && echo "Health OK" || echo "Health check failed"


