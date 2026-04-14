#!/usr/bin/env bash
# Run this ONCE to push sensitive secrets to Google Secret Manager,
# then Cloud Run will pull them automatically at startup.
#
# Usage: ./setup-secrets.sh
# Requires: gcloud CLI logged in, project set to recruit-squad-7d8e1

set -euo pipefail

PROJECT_ID="recruit-squad-7d8e1"
REGION="us-central1"
SERVICE_NAME="recruitsquad-backend"

# Source the backend .env to get values
set -a; source "$(dirname "$0")/backend/.env"; set +a

create_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "${name}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "  Updating secret: ${name}"
    printf '%s' "${value}" | gcloud secrets versions add "${name}" \
      --project="${PROJECT_ID}" --data-file=-
  else
    echo "  Creating secret: ${name}"
    printf '%s' "${value}" | gcloud secrets create "${name}" \
      --project="${PROJECT_ID}" --replication-policy="automatic" --data-file=-
  fi
}

echo "==> Pushing secrets to Secret Manager..."
create_secret "OPENAI_API_KEY"         "${OPENAI_API_KEY}"
create_secret "FIREBASE_PRIVATE_KEY"   "${FIREBASE_PRIVATE_KEY}"
create_secret "SMTP_PASS"              "${SMTP_PASS}"
create_secret "GITHUB_TOKEN"           "${GITHUB_TOKEN}"
create_secret "SERPER_API_KEY"         "${SERPER_API_KEY}"

echo ""
echo "==> Granting Cloud Run service account access to secrets..."
SA="firebase-adminsdk-fbsvc@${PROJECT_ID}.iam.gserviceaccount.com"
for secret in OPENAI_API_KEY FIREBASE_PRIVATE_KEY SMTP_PASS GITHUB_TOKEN SERPER_API_KEY; do
  gcloud secrets add-iam-policy-binding "${secret}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet
done

echo ""
echo "==> Updating Cloud Run service to mount secrets as env vars..."
gcloud run services update "${SERVICE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --update-secrets="\
OPENAI_API_KEY=OPENAI_API_KEY:latest,\
FIREBASE_PRIVATE_KEY=FIREBASE_PRIVATE_KEY:latest,\
SMTP_PASS=SMTP_PASS:latest,\
GITHUB_TOKEN=GITHUB_TOKEN:latest,\
SERPER_API_KEY=SERPER_API_KEY:latest"

echo ""
echo "==> Done! Secrets are now injected into Cloud Run at startup."
