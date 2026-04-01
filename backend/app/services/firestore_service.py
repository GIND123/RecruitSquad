from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore

from app.models.schemas import CandidateProfile


def _get_app() -> firebase_admin.App:
    """Return existing Firebase app or initialise a new one."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.environ["FIREBASE_PROJECT_ID"],
        "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    return firebase_admin.initialize_app(cred)


def get_db() -> firestore.Client:
    _get_app()
    return firestore.client()


# ── Jobs ─────────────────────────────────────────────────────────────────────

def get_job(job_id: str) -> dict | None:
    db = get_db()
    doc = db.collection("jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


def update_job(job_id: str, data: dict) -> None:
    db = get_db()
    db.collection("jobs").document(job_id).set({
        **data,
        "updated_at": datetime.now(timezone.utc),
    }, merge=True)


# ── Candidates ───────────────────────────────────────────────────────────────

def persist_candidates(job_id: str, candidates: list[CandidateProfile]) -> list[str]:
    """
    Write each CandidateProfile into jobs/{job_id}/candidates.
    Returns list of created candidate_ids.
    """
    db = get_db()
    col = db.collection("jobs").document(job_id).collection("candidates")
    ids: list[str] = []

    for candidate in candidates:
        candidate_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        doc = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "name": candidate.name,
            "email": candidate.email or "",
            "github_url": candidate.github_url or "",
            "linkedin_url": candidate.linkedin_url,
            "location": candidate.location or "",
            "pipeline_stage": "SOURCED",
            "source_score": 0.0,
            "github_signals": {
                "languages": candidate.languages,
                "top_repos": candidate.top_repos,
                "commit_frequency": "",
                "profile_summary": candidate.bio or "",
            },
            "source": candidate.source,
            "shortlisted": False,
            "behavioral_complete": False,
            "oa_submitted_at": None,
            "composite_score": None,
            "rank": None,
            "interview_status": "PENDING",
            "created_at": now,
            "updated_at": now,
        }

        col.document(candidate_id).set(doc)
        ids.append(candidate_id)

    return ids


def get_candidates(job_id: str) -> list[dict]:
    db = get_db()
    docs = (
        db.collection("jobs")
        .document(job_id)
        .collection("candidates")
        .order_by("rank")
        .stream()
    )
    return [d.to_dict() for d in docs]


def update_candidate(job_id: str, candidate_id: str, data: dict) -> None:
    db = get_db()
    db.collection("jobs").document(job_id).collection("candidates").document(
        candidate_id
    ).update({**data, "updated_at": datetime.now(timezone.utc)})
