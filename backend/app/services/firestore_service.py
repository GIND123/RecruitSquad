from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore, storage

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
    bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "")
    options = {"storageBucket": bucket_name} if bucket_name else {}
    return firebase_admin.initialize_app(cred, options)


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


def find_candidate_by_id(candidate_id: str) -> dict | None:
    """
    Look up a candidate across all jobs using a collection-group query.
    Returns the full candidate dict (including job_id) or None.
    """
    db = get_db()
    try:
        docs = (
            db.collection_group("candidates")
            .where("candidate_id", "==", candidate_id)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict() or None
    except Exception:
        # Fallback: sequential scan (dev/small datasets)
        for job_doc in db.collection("jobs").stream():
            doc = (
                db.collection("jobs")
                .document(job_doc.id)
                .collection("candidates")
                .document(candidate_id)
                .get()
            )
            if doc.exists:
                return doc.to_dict()
    return None


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


def find_candidate_by_oa_token(oa_token: str) -> dict | None:
    """
    Search all jobs' candidates sub-collections for a matching oa_token.
    Returns { job_id, candidate_id } or None if not found.

    Firestore does NOT support cross-collection-group queries on sub-collection
    fields without a composite index; this implementation uses a collection-group
    query which requires the 'candidates' collection group index in Firebase Console.
    Falls back to a sequential scan if the index is unavailable.
    """
    db = get_db()
    try:
        docs = (
            db.collection_group("candidates")
            .where("oa_token", "==", oa_token)
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict() or {}
            return {
                "job_id":       data.get("job_id", ""),
                "candidate_id": data.get("candidate_id", doc.id),
            }
    except Exception:
        # Fallback: iterate all jobs (slow, only for small datasets / dev)
        jobs_docs = db.collection("jobs").stream()
        for job_doc in jobs_docs:
            job_id = job_doc.id
            cands = (
                db.collection("jobs")
                .document(job_id)
                .collection("candidates")
                .where("oa_token", "==", oa_token)
                .limit(1)
                .stream()
            )
            for c in cands:
                data = c.to_dict() or {}
                return {
                    "job_id":       job_id,
                    "candidate_id": data.get("candidate_id", c.id),
                }
    return None


def get_all_jobs() -> list[dict]:
    """Return all job documents (used by audit and reporting endpoints)."""
    db = get_db()
    return [doc.to_dict() for doc in db.collection("jobs").stream()]


def inject_seed_candidate(job_id: str, email: str, name: str = "Test Candidate") -> str:
    """
    Insert a hardcoded candidate into a job's candidates sub-collection.
    Returns the new candidate_id.
    Used to automatically enrol a fixed email into every posted job.
    """
    db = get_db()
    candidate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    doc = {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "name": name,
        "email": email,
        "github_url": "",
        "linkedin_url": None,
        "location": "Remote",
        "pipeline_stage": "SOURCED",
        "source_score": 0.0,
        "source_signals": {},
        "github_signals": {
            "languages": [],
            "top_repos": [],
            "commit_frequency": "",
            "profile_summary": "",
            "followers": 0,
        },
        "source": "manual",
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

    db.collection("jobs").document(job_id).collection("candidates").document(candidate_id).set(doc)
    return candidate_id


def upload_resume_to_storage(job_id: str, candidate_id: str, file_bytes: bytes, filename: str) -> str:
    """
    Upload a resume file to Firebase Storage.
    Returns the public download URL (with token for direct browser access).
    Path: resumes/{job_id}/{candidate_id}/{filename}
    """
    _get_app()
    bucket = storage.bucket()
    blob_path = f"resumes/{job_id}/{candidate_id}/{filename}"
    blob = bucket.blob(blob_path)

    content_type = "application/pdf"
    if filename.lower().endswith(".doc"):
        content_type = "application/msword"
    elif filename.lower().endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url


def upload_interview_feedback(
    job_id: str,
    candidate_id: str,
    round_number: int,
    feedback_data: dict,
) -> str:
    """
    Upload interview feedback JSON to Firebase Storage.
    Path: interview_feedback/{job_id}/{candidate_id}/round_{round_number}.json
    Returns the public URL.
    """
    import json as _json

    _get_app()
    bucket = storage.bucket()
    blob_path = f"interview_feedback/{job_id}/{candidate_id}/round_{round_number}.json"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(_json.dumps(feedback_data), content_type="application/json")
    blob.make_public()
    return blob.public_url


def get_interview_feedback_from_storage(
    job_id: str,
    candidate_id: str,
    round_number: int,
) -> dict | None:
    """Download a single interview feedback JSON from Firebase Storage."""
    import json as _json

    _get_app()
    bucket = storage.bucket()
    blob_path = f"interview_feedback/{job_id}/{candidate_id}/round_{round_number}.json"
    blob = bucket.blob(blob_path)
    try:
        data = blob.download_as_text()
        return _json.loads(data)
    except Exception:
        return None


def get_all_interview_feedbacks(
    job_id: str,
    candidate_id: str,
    total_rounds: int,
) -> list[dict]:
    """Fetch all interview feedback JSONs for a candidate (rounds 1..total_rounds)."""
    return [
        fb
        for i in range(1, total_rounds + 1)
        for fb in [get_interview_feedback_from_storage(job_id, candidate_id, i)]
        if fb is not None
    ]


def find_candidate_by_referral_token(job_id: str, token: str) -> str | None:
    """Return candidate_id for a candidate in job_id whose referral_token matches."""
    db = get_db()
    docs = (
        db.collection("jobs")
        .document(job_id)
        .collection("candidates")
        .where("referral_token", "==", token)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict() or {}
        return data.get("candidate_id", doc.id)
    return None


def create_applied_candidate(
    job_id: str,
    name: str,
    email: str,
    resume_url: str,
    resume_filename: str,
    candidate_id: str | None = None,
    is_referred: bool = False,
    referral_token_used: str | None = None,
    salary_expectation: float | None = None,
    current_location: str = "",
    open_to_relocation: bool = False,
) -> str:
    """
    Create a candidate document for someone who applied via the public portal.
    pipeline_stage is set to APPLIED. Returns the candidate_id.
    Pass candidate_id explicitly when the ID was already used (e.g. for Storage upload path).
    """
    db = get_db()
    if not candidate_id:
        candidate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    doc = {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "name": name,
        "email": email,
        "resume_url": resume_url,
        "resume_filename": resume_filename,
        "github_url": "",
        "linkedin_url": None,
        "location": "",
        "pipeline_stage": "APPLIED",
        "source_score": 0.0,
        "source_signals": {},
        "github_signals": {
            "languages": [],
            "top_repos": [],
            "commit_frequency": "",
            "profile_summary": "",
            "followers": 0,
        },
        "source": "portal",
        "is_referred": is_referred,
        "referral_token_used": referral_token_used,
        "salary_expectation": salary_expectation,
        "current_location": current_location,
        "open_to_relocation": open_to_relocation,
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

    db.collection("jobs").document(job_id).collection("candidates").document(candidate_id).set(doc)
    return candidate_id