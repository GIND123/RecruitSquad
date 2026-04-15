# RecruitSquad

AI-assisted recruiting platform with:
- `frontend/`: candidate + manager web app (React + Vite + Firebase Auth)
- `backend/`: main orchestration API (FastAPI + LangGraph + Firestore)
- `backend/email-faq-agent/`: email and FAQ microservice (FastAPI + Kafka + Gemini)

This README is a technical reference generated from the current codebase state in this repository on **April 15, 2026**.

## 1. Repository Structure

```text
RecruitSquad/
  backend/
    app/
      agents/            # A1, A2, A3, A4, A5, A7
      controllers/       # API routes: jobs, chat, orgs
      dependencies/      # Firebase auth + manager role guard
      graphs/            # Graph1, Graph2, Graph3, Graph4 orchestrators
      models/            # Pydantic schemas + TypedDict states
      services/          # Firestore, email client, GitHub, Serper
      utils/             # sourcing/search helpers, stackexchange helpers
      main.py            # FastAPI app entry
    tests/
    email-faq-agent/     # separate microservice (also has app/, tests/)
  frontend/
    src/app/
      components/
      contexts/
      pages/
      services/
      routes.tsx
    seed-manager.mjs   # one-time script to bootstrap first manager account
  docs/
  deploy.sh            # all-in-one: secrets + Docker + Cloud Run + Firebase Hosting
  setup-secrets.sh     # standalone: push .env secrets to GCP Secret Manager only
```

## 2. Architecture Overview

RecruitSquad is designed as a staged hiring pipeline:

1. Manager creates a job.
2. Graph 1 sources and scores candidates.
3. Manager or portal flow starts screening (OA + behavioral).
4. Graph 2 scores candidates and routes to reject vs interview scheduling.
5. Interview feedback triggers Graph 4 for round progression.
6. Final-round pass triggers Graph 3 for market analysis and final coordination.
7. Audit report can be generated on-demand by A7.

Core storage and identity:
- Firestore collections: `jobs`, `jobs/{job_id}/candidates`, `organizations`, `users`.
- Firebase Auth for manager-protected endpoints.
- OA/chat/scheduling use tokenized public flows (`oa_token`, `candidate_id`).

## 3. Backend API (`backend/app`)

### 3.1 Entry and middleware
- `app.main`:
  - loads environment variables via `python-dotenv`
  - initializes Firebase Admin SDK at startup
  - applies CORS for local + Firebase hosting + optional `APP_URL`
  - mounts routers:
    - `/api/jobs`
    - `/api/chat`
    - `/api/orgs`

### 3.2 Auth model
- `get_current_user`: verifies Firebase bearer token.
- `require_manager`: verifies Firestore `users/{uid}.role == "manager"` and merges org metadata.

### 3.3 API surface (main routes)

Jobs and candidates:
- `POST /api/jobs` (manager): create job and enqueue Graph 1.
- `GET /api/jobs`: list jobs (optional `org_id` filter).
- `GET /api/jobs/my-applications` (auth): candidate history by token email.
- `GET /api/jobs/{job_id}`: job detail.
- `POST /api/jobs/{job_id}/apply`: candidate application (multipart resume upload), dedupe by email, triggers A2 OA generation.
- `GET /api/jobs/{job_id}/candidates` (manager): list pipeline candidates.
- `POST /api/jobs/{job_id}/candidates/{candidate_id}/send-invite` (manager): outreach invite (optional referral tokenized link).
- `POST /api/jobs/{job_id}/candidates/{candidate_id}/start-screening` (manager): force A2 generation.
- `POST /api/jobs/{job_id}/candidates/{candidate_id}/retry-screening` (manager): rerun Graph 2.
- `POST /api/jobs/{job_id}/candidates/{candidate_id}/interview-feedback` (manager): enqueue Graph 4 round processing.
- `GET /api/jobs/{job_id}/report` (manager): run A7 audit + return report payload.
- `POST /api/jobs/referrals`: referral candidate stub creation.

OA and scheduling:
- `GET /api/jobs/oa/{oa_token}`: fetch OA questions.
- `POST /api/jobs/oa/{oa_token}/submit`: persist OA answers and enqueue Graph 2.
- `GET /api/jobs/schedule/{candidate_id}`: scheduling page context.
- `POST /api/jobs/schedule/{candidate_id}/confirm`: slot confirmation + Google Calendar event attempt + confirmation email.

Behavioral chat:
- `GET /api/chat/{oa_token}`: chat context.
- `POST /api/chat/{oa_token}/message`: conversational turn with A2; when complete, async retriggers Graph 2.

Organizations:
- `GET /api/orgs`: list orgs.
- `GET /api/orgs/{org_id}`: org detail.
- `POST /api/orgs` (auth): create org + manager role assignment.
- `POST /api/orgs/{org_id}/join` (auth): join org as manager.

## 4. Orchestration Methodology (LangGraph)

### Graph 1: Sourcing pipeline (`graph1.py`)
Flow:
- A1 `run_sourcing_hunter`
- A5 `compute_source_scores`
- job status update to `SOURCED`

Method:
- Parse JD into tech stack, locations, experience.
- Search GitHub and LinkedIn in parallel with local-first 2-pass strategy.
- Persist candidates.
- Score source quality and language match.

### Graph 2: Screening pipeline (`graph2.py`)
Flow:
- A2 OA evaluation (`evaluate_oa_responses` called in node)
- A5 scoring engine
- Routing:
  - OA failed -> reject email
  - OA passed but behavioral incomplete -> hold in `AWAITING_BEHAVIORAL`
  - OA + behavioral passed and shortlisted -> schedule + invite

Method:
- OA answers are scored, then combined with behavioral and fit metrics.
- Shortlisting gate for interview invite is intentionally **not** composite-threshold based pre-interview:
  - `oa_passed == True`
  - `behavioral_score >= 70`
- Supports reschedule loop up to 3 attempts.

### Graph 3: Final coordination + market analysis (`graph3.py`)
Flow:
- A5 final ranking
- A4 market salary analysis
- A6 salary report to manager
- A3 scheduling links for shortlisted
- A6 interview invitations

Method:
- Re-ranks eligible candidates with thresholding + invite cap.
- Generates percentile salary report (`p25/p50/p75/p90`) and budget warning.

### Graph 4: Interview round progression (`graphs/__init__.py`)
Flow:
- A5 `update_interview_scorecard`
- Routes by `next_action`:
  - `SCHEDULE_NEXT_ROUND`: generate links and notify
  - `MARKET_ANALYSIS`: notify manager and trigger Graph 3
  - `REJECTED`: notify both

Method:
- Round number and total rounds are derived from persisted state when needed.
- Structured feedback is stored and used to recompute composite score after each round.

## 5. Agent Methodology

### A1 Sourcing Hunter
- JD parsing with OpenAI.
- GitHub + LinkedIn sourcing with configurable search strictness:
  - tight, medium, loose profiles based on `max_results`.
- Merge strategy:
  - GitHub and LinkedIn profiles merged by normalized name key.
- Persistence:
  - writes into `jobs/{job_id}/candidates`.

### A2 OA + Behavioral
- Generates OA questions (`MCQ`, `CODING`, `TEXT`) and behavioral STAR questions.
- Creates `oa_token`, OA link, and chat link per candidate.
- Conducts per-message behavioral chat with strict off-topic enforcement.
- Evaluates OA with OpenAI JSON response; completion-rate fallback when unavailable.

### A3 Interview Coordinator
- Creates Calendly scheduling links (or fallback self-hosted link).
- Creates Google Calendar events on slot confirmation (returns event link).
- Supports multiple credential sources for Google service accounts.

### A4 Market Analyst
- Salary research via Serper multi-query strategy.
- OpenAI synthesizes percentile compensation estimates.
- Fallback heuristic model if OpenAI unavailable.
- Builds manager report payload and persists salary report.

### A5 Scoring Engine
Key thresholds:
- `OA_PASS_THRESHOLD = 70`
- `BEHAVIORAL_PASS_THRESHOLD = 70`
- `SHORTLIST_SCORE_THRESHOLD = 75` (for post-interview final ranking)

Composite methodologies:
- Legacy v1/v2 helpers are retained.
- Current v3 model (max 100):
  - Resume/JD fit: 10
  - Budget fit: 5
  - Location fit: 5
  - Experience fit: 5
  - Referral bonus: 5
  - OA: 5
  - Behavioral: 5
  - Interview rounds aggregate: 60 (split by configured rounds)

Additional methodology:
- Resume/JD CMS score from uploaded resumes (PDF/DOCX/text extractors).
- Behavioral gating logic for pre-interview shortlisting.
- Interview feedback scoring weights:
  - technical 30%
  - communication 20%
  - problem solving 25%
  - cultural fit 15%
  - recommendation 10%

### A6 Email Dispatch (Service, not a LangGraph Agent)
- `backend/app/services/a6_client.py` — not an agent directory, but a shared email dispatch utility used by all graphs.
- Two delivery paths (checked in order):
  1. **Direct SMTP** — used when `SMTP_USER` + `SMTP_PASS` are set (Gmail SSL port 465).
  2. **Email-FAQ microservice** — fallback to `EMAIL_AGENT_URL` (default `localhost:8001`) when SMTP credentials are absent.
- Fire-and-forget: logs failures, never raises, so graph execution continues even if email fails.
- Key helpers: `send_outreach_email`, `send_oa_invite`, `send_application_acknowledgment`, `send_interview_invite`, `send_rejection`, `send_salary_report_to_manager`, `send_generic_email`, `send_interview_confirmation`.
- `DRY_RUN=true` skips all delivery (useful in CI).

### A7 Audit
- Read-only audit over job and candidate state.
- Computes funnel metrics, averages, conversion rates.
- Flags anomalies (stuck OA, missing composite, etc.).
- Optional OpenAI-generated summary with template fallback.

## 6. Data Model and Persistence

Primary collections:
- `jobs/{job_id}`
- `jobs/{job_id}/candidates/{candidate_id}`
- `organizations/{org_id}`
- `users/{uid}`

Candidate document methodology:
- Source and enrichment fields:
  - `source`, `source_score`, `source_signals`, `github_signals`
- Screening fields:
  - `oa_token`, `oa_questions`, `oa_responses`, `oa_score`, `oa_passed`
  - `behavioral_questions`, `behavioral_transcript`, `behavioral_score`, `behavioral_complete`
- Scoring/ranking fields:
  - `resume_jd_score`, `composite_score`, `score_breakdown`, `rank`, `shortlisted`
- Interview fields:
  - `interview_rounds`, `current_round`, `total_rounds`, `overall_interview_result`
  - `calendly_link`, `interview_slot`, `interview_timezone`, `zoom_url`
- Lifecycle fields:
  - `pipeline_stage`, `created_at`, `updated_at`

Storage conventions:
- Resume uploads:
  - `resumes/{job_id}/{candidate_id}/{filename}`
- Structured interview feedback uploads:
  - `interview_feedback/{job_id}/{candidate_id}/round_{n}.json`

## 7. Frontend (`frontend/src/app`)

### 7.1 Routing model
Public routes:
- `/jobs`, `/jobs/:id`, `/jobs/:id/apply`
- `/oa/:token`, `/oa/:token/chat`
- `/schedule/:candidateId`
- `/employer`, `/employer/new`, `/login`

Protected routes:
- `/profile` (authenticated)
- `/manager`, `/manager/create-job`, `/manager/jobs/:jobId` (manager role required)

### 7.2 Frontend methodology
- API integration via `apiService.ts` with:
  - plain requests
  - auth requests with Firebase ID token
- `AuthContext`:
  - subscribes to Firebase auth state
  - reads Firestore profile for role/org context
  - includes race-condition fallback for first-login profile propagation
- Manager flow:
  - create jobs
  - inspect pipeline
  - submit interview feedback
  - trigger retry/invite actions
  - generate reports
- Candidate flow:
  - browse jobs
  - apply with resume and optional referral
  - complete OA
  - complete behavioral chat
  - confirm interview slot
  - track applications in profile

### 7.3 Seeding the first manager account

`frontend/seed-manager.mjs` is a one-time Node.js utility that creates a Firebase Auth account and writes a `users/{uid}` Firestore document with `role: "manager"`. Run it before the first login when bootstrapping a new Firebase project:

```bash
# Edit MANAGER_EMAIL and MANAGER_PASSWORD at the top of the file first
node frontend/seed-manager.mjs
```

## 8. Email FAQ Microservice (`backend/email-faq-agent`)

FastAPI service with endpoints for:
- direct send (`/send-email`)
- queue (`/enqueue-email`)
- AI task routing (`/agent/*`)

Key modules:
- `app/services/email_service.py`: SMTP delivery
- `app/agent/orchestrator.py`: send mode decision (immediate vs queued)
- `app/agent/scheduling_agent.py`: Gemini tool-calling flow for scheduling
- `app/kafka/*`: producer/consumer flow for queued jobs

Deployment mode:
- docker-compose includes `zookeeper`, `kafka`, `email-agent`, `consumer`.

## 9. Environment Configuration

### 9.1 Backend (`backend/.env`)
Create `backend/.env` (no `.env.example` exists — use the table below as reference). Core keys:
- OpenAI: `OPENAI_API_KEY`
- Firebase: `FIREBASE_PROJECT_ID`, `FIREBASE_PRIVATE_KEY`, `FIREBASE_CLIENT_EMAIL`, `FIREBASE_STORAGE_BUCKET`
- SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL`
- Sourcing/market: `GITHUB_TOKEN`, `SERPER_API_KEY`, `STACKEXCHANGE_API_KEY`
- App: `APP_URL`, `API_URL`, `COMPANY_NAME`, `MANAGER_EMAIL`, `EMAIL_AGENT_URL`, `DRY_RUN`
- Scheduling integrations: `CALENDLY_API_KEY`, `CALENDLY_EVENT_TYPE_UUID`, `GOOGLE_*`

### 9.2 Frontend (`frontend/.env`)
Required keys:
- `VITE_API_URL`
- Firebase client config:
  - `VITE_FIREBASE_API_KEY`
  - `VITE_FIREBASE_AUTH_DOMAIN`
  - `VITE_FIREBASE_PROJECT_ID`
  - `VITE_FIREBASE_STORAGE_BUCKET`
  - `VITE_FIREBASE_MESSAGING_SENDER_ID`
  - `VITE_FIREBASE_APP_ID`
  - `VITE_FIREBASE_MEASUREMENT_ID`

### 9.3 Email agent (`backend/email-faq-agent/.env`)
Expected settings map to:
- SMTP, Kafka, Gemini, log/app env fields in `app/config.py`.

## 10. Local Runbook

### macOS / Linux

#### Backend API
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install idb   # required by Firebase — not auto-installed on some Node versions
npm install
npm run dev
```

#### Email FAQ agent
```bash
cd backend/email-faq-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Optional Kafka stack:
```bash
cd backend/email-faq-agent
docker compose up -d zookeeper kafka
docker compose up --build email-agent consumer
```

### Windows (PowerShell)

#### Backend API
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```powershell
cd frontend
npm install idb
npm install
npm run dev
```

#### Email FAQ agent
```powershell
cd backend\email-faq-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Optional Kafka stack:
```powershell
cd backend\email-faq-agent
docker compose up -d zookeeper kafka
docker compose up --build email-agent consumer
```

## 11. Deployment

### Prerequisites
- `gcloud` CLI: `gcloud auth login && gcloud auth configure-docker && gcloud config set project recruit-squad-7d8e1`
- `firebase` CLI: `firebase login`
- `backend/.env` populated with all required keys

### Option A — All-in-one (`deploy.sh`)

Handles secrets, Docker build, Cloud Run deploy, and Firebase Hosting in one script:

```bash
# Deploy backend only
./deploy.sh backend

# Deploy frontend only (requires VITE_API_URL set in frontend/.env)
./deploy.sh frontend

# Deploy both (prompts to update VITE_API_URL between steps)
./deploy.sh all
```

### Option B — Secrets only (`setup-secrets.sh`)

Pushes secret values from `backend/.env` to GCP Secret Manager without rebuilding or deploying. Useful when rotating credentials:

```bash
./setup-secrets.sh
```

### What gets deployed
- **Backend** → Google Cloud Run (`recruitsquad-backend`, `us-central1`), image via Cloud Build
- **Frontend** → Firebase Hosting (`recruit-squad-7d8e1.web.app` / `.firebaseapp.com`)
- **Secrets** → GCP Secret Manager (keys: `RS_OPENAI_API_KEY`, `RS_FIREBASE_PRIVATE_KEY`, `RS_SMTP_PASS`, `RS_GITHUB_TOKEN`, `RS_SERPER_API_KEY`)

### After first backend deploy
Update `frontend/.env`:
```
VITE_API_URL=https://<cloud-run-url>
```
Then run `./deploy.sh frontend`.

## 12. Testing and Current Health (April 15, 2026)

Commands run:
- `backend`: `python -m pytest -q`
- `backend/tests only`: `python -m pytest -q tests`
- `frontend`: `npm run build`

Observed status:
- Backend full test collection currently fails.
- Backend focused tests currently fail in key suites.
- Frontend production build currently fails.

Root causes identified:
- Cross-package test import conflicts due two top-level `app` packages (`backend/app` and `backend/email-faq-agent/app`) in one test run context.
- `email-faq-agent` settings reject unrelated environment keys during test collection.
- Graph4 expects `create_zoom_meeting` from Agent3, but Agent3 currently exposes `create_calendly_link` and `create_google_calendar_event` only.
- Graph4 tests monkeypatch `app.graphs.run_market_analyst`, but that symbol is not exported in `app.graphs`.
- A1 tests require outbound OpenAI connectivity; in restricted/no-network environments these fail by connection error.
- Frontend build fails with unresolved dependency: `idb` required by Firebase package resolution path.

## 13. Known Technical Debt and Risks

- `frontend/src/app/contexts/JobContext.tsx` is legacy localStorage/mock state and is not aligned with the API-backed architecture.
- Existing docs in `docs/` contain stale assumptions relative to active orchestration code.
- Some files contain non-ASCII mojibake text; standardizing encoding to UTF-8 without corruption is recommended.
- End-to-end reliability still depends on external services (OpenAI, Serper, Firebase, SMTP, Calendly, Google Calendar).
- **ZOOM_* env vars are broken**: `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` appear in `backend/.env.example` but `create_zoom_meeting` is never implemented in Agent3. These variables have no effect until the Zoom integration is built out.
- **Legacy backup files**: `graph1 2.py`, `graph2 2.py`, `graph3 2.py`, `chat 2.py`, `auth 2.py`, `agent2/__init__ 2.py`, etc. exist in the repo as space-named duplicates and should be deleted to avoid confusion.
- **`VITE_API_URL` missing from `frontend/.env.example`**: The frontend requires this key to connect to the backend, but it is not listed in the example file. Add `VITE_API_URL=http://localhost:8000` to `frontend/.env.example`.
- **A6 is not an agent**: References to "A6" in graph flow descriptions (Graph 3) refer to the email dispatch service (`services/a6_client.py`), not a LangGraph agent. There is no `agents/agent6/` directory.

