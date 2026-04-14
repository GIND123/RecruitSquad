#!/usr/bin/env bash
# RecruitSquad deployment script
# Usage: ./deploy.sh [backend|frontend|all]
#
# Prerequisites:
#   gcloud CLI:  gcloud auth login && gcloud auth configure-docker
#                gcloud config set project recruit-squad-7d8e1
#   firebase CLI: firebase login

set -euo pipefail

PROJECT_ID="recruit-squad-7d8e1"
REGION="us-central1"
SERVICE_NAME="recruitsquad-backend"
IMAGE="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Secret Manager helpers ────────────────────────────────────────────────────

# Read a value from the .env file by key (safe for values containing spaces/special chars)
read_env() {
  local key="$1"
  grep "^${key}=" "${SCRIPT_DIR}/backend/.env" | head -1 | cut -d'=' -f2-
}

upsert_secret() {
  local name="$1"
  local value="$2"
  if gcloud secrets describe "${name}" --project="${PROJECT_ID}" &>/dev/null 2>&1; then
    printf '%s' "${value}" | gcloud secrets versions add "${name}" \
      --project="${PROJECT_ID}" --data-file=- --quiet
  else
    printf '%s' "${value}" | gcloud secrets create "${name}" \
      --project="${PROJECT_ID}" --replication-policy="automatic" --data-file=- --quiet
  fi
}

push_secrets() {
  echo "  Pushing secrets to Secret Manager..."
  upsert_secret "RS_OPENAI_API_KEY"       "$(read_env OPENAI_API_KEY)"
  upsert_secret "RS_FIREBASE_PRIVATE_KEY" "$(read_env FIREBASE_PRIVATE_KEY)"
  upsert_secret "RS_SMTP_PASS"            "$(read_env SMTP_PASS)"
  upsert_secret "RS_GITHUB_TOKEN"         "$(read_env GITHUB_TOKEN)"
  upsert_secret "RS_SERPER_API_KEY"       "$(read_env SERPER_API_KEY)"

  # Grant the Cloud Run default compute SA access to read secrets
  PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
  CR_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  for secret in RS_OPENAI_API_KEY RS_FIREBASE_PRIVATE_KEY RS_SMTP_PASS RS_GITHUB_TOKEN RS_SERPER_API_KEY; do
    gcloud secrets add-iam-policy-binding "${secret}" \
      --project="${PROJECT_ID}" \
      --member="serviceAccount:${CR_SA}" \
      --role="roles/secretmanager.secretAccessor" \
      --quiet 2>/dev/null || true
  done
  echo "  Secrets pushed."
}

# ── Backend deploy ────────────────────────────────────────────────────────────

deploy_backend() {
  echo "==> Pushing secrets to Secret Manager..."
  push_secrets

  echo "==> Building and pushing Docker image..."
  cd "${SCRIPT_DIR}/backend"
  gcloud builds submit --tag "${IMAGE}" .
  cd "${SCRIPT_DIR}"

  echo "==> Deploying to Cloud Run..."
  gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE}" \
    --platform managed \
    --region "${REGION}" \
    --allow-unauthenticated \
    --port 8080 \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "\
FIREBASE_PROJECT_ID=recruit-squad-7d8e1,\
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-fbsvc@recruit-squad-7d8e1.iam.gserviceaccount.com,\
FIREBASE_STORAGE_BUCKET=recruit-squad-7d8e1.firebasestorage.app,\
SMTP_HOST=smtp.gmail.com,\
SMTP_PORT=465,\
SMTP_USER=alice.ai.hr.agent@gmail.com,\
FROM_EMAIL=alice.ai.hr.agent@gmail.com,\
GOOGLE_CALENDAR_ID=abhinavkumar333.ak@gmail.com,\
APP_URL=https://${PROJECT_ID}.web.app,\
COMPANY_NAME=RecruitSquad,\
EMAIL_AGENT_URL=http://localhost:8001,\
MANAGER_EMAIL=recruitsquad.manager@gmail.com,\
DRY_RUN=false" \
    --set-secrets "\
OPENAI_API_KEY=RS_OPENAI_API_KEY:latest,\
FIREBASE_PRIVATE_KEY=RS_FIREBASE_PRIVATE_KEY:latest,\
SMTP_PASS=RS_SMTP_PASS:latest,\
GITHUB_TOKEN=RS_GITHUB_TOKEN:latest,\
SERPER_API_KEY=RS_SERPER_API_KEY:latest"

  BACKEND_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform managed --region "${REGION}" \
    --format "value(status.url)")

  echo ""
  echo "==> Backend live at: ${BACKEND_URL}"
  echo ""
  echo "    Update frontend/.env:"
  echo "      VITE_API_URL=${BACKEND_URL}"
}

# ── Frontend deploy ───────────────────────────────────────────────────────────

deploy_frontend() {
  echo "==> Building frontend..."
  cd "${SCRIPT_DIR}/frontend"
  npm run build
  cd "${SCRIPT_DIR}"

  echo "==> Deploying to Firebase Hosting..."
  firebase deploy --only hosting --project "${PROJECT_ID}"

  echo ""
  echo "==> Frontend live at:"
  echo "    https://${PROJECT_ID}.web.app"
  echo "    https://${PROJECT_ID}.firebaseapp.com"
}

# ── Entry point ───────────────────────────────────────────────────────────────

TARGET="${1:-all}"

case "$TARGET" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend ;;
  all)
    deploy_backend
    echo ""
    read -r -p "Update VITE_API_URL in frontend/.env with the backend URL above, then press Enter..."
    deploy_frontend
    ;;
  *)
    echo "Usage: $0 [backend|frontend|all]"
    exit 1
    ;;
esac

echo ""
echo "==> Done!"
