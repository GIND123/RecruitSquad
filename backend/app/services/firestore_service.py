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

    cred = credentials.Certificate(
        {
            "type": "service_account",
            "project_id": os.environ["FIREBASE_PROJECT_ID"],
            "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
            "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    return firebase_admin.initialize_app(cred)


def get_db() -> firestore.Client:
    _get_app()
    return firestore.client()


def get_job(job_id: str) -> dict | None:
    db = get_db()
    doc = db.collection("jobs").document(job_id).get()
    return doc.to_dict() if doc.exists else None


def update_job(job_id: str, data: dict) -> None:
    db = get_db()
    db.collection("jobs").document(job_id).set(
        {
            **data,
            "updated_at": datetime.now(timezone.utc),
        },
        merge=True,
    )


def persist_candidates(job_id: str, candidates: list[CandidateProfile]) -> list[str]:
    """Write each CandidateProfile into jobs/{job_id}/candidates."""
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
            "source_signals": {},
            "github_signals": {
                "languages": candidate.languages,
                "top_repos": candidate.top_repos,
                "commit_frequency": "",
                "profile_summary": candidate.bio or "",
                "followers": candidate.followers,
            },
            "source": candidate.source,
            "shortlisted": False,
            "behavioral_complete": False,
            "behavioral_score": 0.0,
            "oa_score": 0.0,
            "oa_passed": False,
            "experience_passed": None,
            "location_passed": None,
            "salary_within_budget": None,
            "oa_submitted_at": None,
            "composite_score": None,
            "rank": None,
            "interview_status": "PENDING",
            "interview_rounds": {},
            "current_round": 0,
            "total_rounds": 0,
            "overall_interview_result": "PENDING",
            "overall_feedback": None,
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
    return [doc.to_dict() for doc in docs]


def get_candidate(job_id: str, candidate_id: str) -> dict | None:
    db = get_db()
    doc = (
        db.collection("jobs")
        .document(job_id)
        .collection("candidates")
        .document(candidate_id)
        .get()
    )
    return doc.to_dict() if doc.exists else None


def update_candidate(job_id: str, candidate_id: str, data: dict) -> None:
    db = get_db()
    (
        db.collection("jobs")
        .document(job_id)
        .collection("candidates")
        .document(candidate_id)
        .update({**data, "updated_at": datetime.now(timezone.utc)})
    )


def save_interview_round(
    job_id: str,
    candidate_id: str,
    candidate_name: str,
    round_number: int,
    result: str,
    feedback: str,
    interviewer_name: str | None,
    total_rounds: int,
    completed_at: datetime | None = None,
    interviewer_id: str | None = None,
) -> None:
    """
    Persist a single interview round under jobs/{job_id}/candidates/{candidate_id}.

    Uses update() — NOT set(merge=True) — so dot-notation field paths
    (e.g. 'interview_rounds.1') are correctly stored as nested map entries
    rather than top-level keys with a literal dot in the name.

    Parameters
    ----------
    completed_at : optional timestamp from the interviewer's form submission.
                   Defaults to utcnow() when not provided.
    interviewer_id : optional portal user ID of the interviewer.
    """
    db = get_db()
    now = completed_at or datetime.now(timezone.utc)
    candidate_ref = (
        db.collection("jobs")
        .document(job_id)
        .collection("candidates")
        .document(candidate_id)
    )

    round_payload = {
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "round_number": round_number,
        "result": result,
        "feedback": feedback,
        "interviewer_name": interviewer_name,
        "interviewer_id": interviewer_id,
        "completed_at": now,
    }

    overall_result = "PENDING"
    overall_feedback = None
    if result == "REJECTED":
        overall_result = "REJECTED"
        overall_feedback = feedback
    elif round_number >= total_rounds:
        overall_result = "SELECTED"
        overall_feedback = feedback

    # update() correctly interprets 'interview_rounds.N' as a nested path.
    payload = {
        f"interview_rounds.{round_number}": round_payload,
        "current_round": round_number,
        "total_rounds": total_rounds,
        "overall_interview_result": overall_result,
        "updated_at": datetime.now(timezone.utc),
    }
    if overall_feedback is not None:
        payload["overall_feedback"] = overall_feedback

    candidate_ref.update(payload)