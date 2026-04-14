from dotenv import load_dotenv
load_dotenv()

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.controllers.chat import router as chat_router
from app.controllers.jobs import router as jobs_router

# Ensure Firebase Admin SDK is initialised at startup so that
# firebase_admin.auth.verify_id_token() works on the first request.
import logging as _logging
try:
    from app.services.firestore_service import get_db as _init_firebase
    _init_firebase()
    _logging.getLogger(__name__).info("[startup] Firebase Admin SDK initialised")
except Exception as _e:
    _logging.getLogger(__name__).error("[startup] Firebase init failed: %s", _e)

app = FastAPI(title="RecruitSquad API")

_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    # Firebase Hosting domains — update APP_URL env var after first deploy
    "https://recruit-squad-7d8e1.web.app",
    "https://recruit-squad-7d8e1.firebaseapp.com",
]
# Allow any custom domain set via APP_URL (e.g. https://recruitsquad.com)
_app_url = os.environ.get("APP_URL", "").rstrip("/")
if _app_url and _app_url not in _ALLOWED_ORIGINS:
    _ALLOWED_ORIGINS.append(_app_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router)
app.include_router(chat_router)
