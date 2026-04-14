from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form

from app.agents.agent2 import run_behavioral_oa
from app.agents.agent7 import run_audit
from app.graphs import run_interview_round_pipeline, run_screening_pipeline, run_sourcing_pipeline
from app.models.schemas import (
    InterviewFeedbackRequest,
    InterviewFeedbackResponse,
    JobCreateRequest,
    JobResponse,
    ReferralRequest,
)
from app.models.states import ScreeningState, SourcingState
from app.services.firestore_service import (
    create_applied_candidate,
    find_candidate_by_id,
    find_candidate_by_referral_token,
    get_all_jobs,
    get_candidate,
    get_candidates,
    get_job,
    inject_seed_candidate,
    update_candidate,
    update_job,
    upload_resume_to_storage,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreateRequest, background_tasks: BackgroundTasks):
    """Create a job and trigger Agent 1 sourcing in the background."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    job_doc = {
        "job_id": job_id,
        "title": payload.title,
        "role_description": payload.role_description,
        "headcount": payload.headcount,
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "locations": payload.locations,
        "experience_min": payload.experience_min,
        "experience_max": payload.experience_max,
        "team": payload.team,
        "total_interview_rounds": payload.total_interview_rounds,
        "referrals_enabled": payload.referrals_enabled,
        "status": "PENDING",
        "candidate_count": 0,
        "created_at": now,
    }
    update_job(job_id, job_doc)
    logger.info("[jobs] created job=%s title=%r", job_id, payload.title)

    # Always enrol the seed candidate so they go through the full pipeline
    _SEED_EMAIL = "ak395@umd.edu"
    seed_id = inject_seed_candidate(job_id, email=_SEED_EMAIL, name="Abhinav Kumar")
    logger.info("[jobs] seed candidate injected job=%s candidate=%s email=%s", job_id, seed_id, _SEED_EMAIL)

    initial_state: SourcingState = {
        "job_id": job_id,
        "jd_text": payload.role_description,
        "tech_stack": [],
        "experience_range": (payload.experience_min, payload.experience_max),
        "locations": payload.locations,
        "sourced_candidates": [],
        "outreach_sent": False,
        "graph1_complete": False,
    }
    background_tasks.add_task(_run_agent1, initial_state)

    return JobResponse(
        job_id=job_id,
        title=payload.title,
        status="PENDING",
        headcount=payload.headcount,
        candidate_count=0,
        created_at=now,
    )


async def _run_agent1(state: SourcingState) -> None:
    """Background task: run the full Graph 1 sourcing pipeline."""
    job_id = state["job_id"]
    try:
        await run_sourcing_pipeline(
            job_id=job_id,
            jd_text=state["jd_text"],
            locations=state["locations"],
            experience_min=state["experience_range"][0],
            experience_max=state["experience_range"][1],
        )
        logger.info("[jobs] Graph1 pipeline complete job=%s", job_id)
    except Exception as exc:
        logger.error("[jobs] Graph1 pipeline failed job=%s: %s", job_id, exc)
        update_job(job_id, {"status": "FAILED", "error": str(exc)})


@router.get("", response_model=list[JobResponse])
async def list_jobs():
    """Return all job postings."""
    jobs = get_all_jobs()
    return [
        JobResponse(
            job_id=j.get("job_id", ""),
            title=j.get("title", ""),
            status=j.get("status", "PENDING"),
            headcount=j.get("headcount", 1),
            candidate_count=j.get("candidate_count", 0),
            created_at=j.get("created_at", datetime.now(timezone.utc)),
        )
        for j in jobs
    ]


@router.get("/{job_id}")
async def get_job_detail(job_id: str):
    """Return a single job document."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


@router.post("/{job_id}/apply", status_code=201)
async def apply_to_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    email: str = Form(...),
    resume: UploadFile = File(...),
    referral_token: str = Form(""),
    salary_expectation: float | None = Form(None),
    current_location: str = Form(""),
    open_to_relocation: bool = Form(False),
):
    """Public endpoint — candidate applies via the job portal with a resume upload."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    file_bytes = await resume.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Resume must be under 5 MB")

    # Check if applicant was referred via a sourced-candidate referral link
    is_referred = False
    if referral_token:
        sourced_id = find_candidate_by_referral_token(job_id, referral_token)
        if sourced_id:
            # Mark the sourced candidate's referral as used (they get scoring boost later)
            update_candidate(job_id, sourced_id, {"referral_used": True})
            is_referred = True
            logger.info("[jobs] referral token matched job=%s sourced_candidate=%s", job_id, sourced_id)

    candidate_id = str(uuid.uuid4())

    # Upload resume to Firebase Storage
    try:
        resume_url = upload_resume_to_storage(
            job_id=job_id,
            candidate_id=candidate_id,
            file_bytes=file_bytes,
            filename=resume.filename or "resume",
        )
    except Exception as exc:
        logger.error("[jobs] resume upload failed job=%s: %s", job_id, exc)
        resume_url = ""

    # Create candidate document with the same candidate_id used for storage
    create_applied_candidate(
        job_id=job_id,
        candidate_id=candidate_id,
        name=name,
        email=email,
        resume_url=resume_url,
        resume_filename=resume.filename or "",
        is_referred=is_referred,
        referral_token_used=referral_token or None,
        salary_expectation=salary_expectation,
        current_location=current_location,
        open_to_relocation=open_to_relocation,
    )

    logger.info("[jobs] portal application job=%s candidate=%s email=%s referred=%s",
                job_id, candidate_id, email, is_referred)

    # Send immediate acknowledgment email
    from app.services.a6_client import send_application_acknowledgment
    background_tasks.add_task(
        send_application_acknowledgment,
        candidate_name=name,
        candidate_email=email,
        role_title=job.get("title", "the position"),
    )

    # Trigger OA generation + invite in background
    background_tasks.add_task(_run_agent2, job_id=job_id, candidate_id=candidate_id)

    return {
        "candidate_id": candidate_id,
        "resume_url": resume_url,
        "message": "Application received. You will receive an email with assessment details shortly.",
    }


@router.get("/{job_id}/candidates")
async def list_candidates(job_id: str):
    """Return all sourced candidates for a job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "candidates": get_candidates(job_id)}


@router.get("/oa/{oa_token}", status_code=200)
async def get_oa(oa_token: str):
    """
    Public endpoint — return OA questions and context for the given token.
    Called by the frontend when the candidate opens their OA link.
    """
    from app.services.firestore_service import find_candidate_by_oa_token
    match = find_candidate_by_oa_token(oa_token)
    if not match:
        raise HTTPException(status_code=404, detail="OA link not found or expired")

    job_id       = match["job_id"]
    candidate_id = match["candidate_id"]

    candidate = get_candidate(job_id, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = get_job(job_id) or {}

    return {
        "oa_token":      oa_token,
        "candidate_name": candidate.get("name", ""),
        "job_title":     job.get("title", ""),
        "job_id":        job_id,
        "oa_questions":  candidate.get("oa_questions", []),
        "already_submitted": bool(candidate.get("oa_submitted_at")),
    }


@router.post("/oa/{oa_token}/submit", status_code=202)
async def submit_oa(
    oa_token: str,
    background_tasks: BackgroundTasks,
    payload: dict = None,
):
    """
    Public endpoint — candidate submits their OA answers.
    Accepts { responses: [{question_id, answer}] } in the request body.
    Persists answers to Firestore then triggers the screening pipeline.
    """
    from app.services.firestore_service import find_candidate_by_oa_token
    match = find_candidate_by_oa_token(oa_token)
    if not match:
        raise HTTPException(status_code=404, detail="OA token not found or already used")

    job_id       = match["job_id"]
    candidate_id = match["candidate_id"]

    candidate = get_candidate(job_id, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if candidate.get("oa_submitted_at"):
        raise HTTPException(status_code=409, detail="OA already submitted")

    # Persist answers alongside a submission timestamp
    responses = (payload or {}).get("responses", [])
    update_candidate(job_id, candidate_id, {
        "oa_responses":    responses,
        "oa_submitted_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("[jobs] OA submitted token=%s job=%s candidate=%s answers=%d",
                oa_token, job_id, candidate_id, len(responses))

    background_tasks.add_task(_run_screening, job_id=job_id, candidate_id=candidate_id)
    return {
        "received":     True,
        "candidate_id": candidate_id,
        "message":      "OA received. Screening pipeline started.",
    }


async def _run_screening(job_id: str, candidate_id: str) -> None:
    """Background task: run the full Graph 2 screening pipeline for one candidate."""
    try:
        await run_screening_pipeline(job_id=job_id, candidate_id=candidate_id)
        logger.info("[jobs] Graph2 pipeline complete job=%s candidate=%s", job_id, candidate_id)
    except Exception as exc:
        logger.error("[jobs] Graph2 pipeline failed job=%s candidate=%s: %s",
                     job_id, candidate_id, exc)


@router.post(
    "/{job_id}/candidates/{candidate_id}/start-screening",
    status_code=202,
)
async def start_screening(
    job_id: str,
    candidate_id: str,
    background_tasks: BackgroundTasks,
):
    """
    Trigger A2 for a single candidate — generates OA + behavioral questions
    and updates pipeline_stage to OA_SENT.
    """
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if not get_candidate(job_id, candidate_id):
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    logger.info("[jobs] start-screening job=%s candidate=%s", job_id, candidate_id)
    background_tasks.add_task(_run_agent2, job_id=job_id, candidate_id=candidate_id)

    return {"message": "Screening started", "candidate_id": candidate_id, "job_id": job_id}


async def _run_agent2(job_id: str, candidate_id: str) -> None:
    from app.services.firestore_service import get_job as _get_job
    job = _get_job(job_id) or {}
    state: ScreeningState = {
        "job_id":               job_id,
        "candidate_id":         candidate_id,
        "jd_text":              str(job.get("role_description") or ""),
        "oa_questions":         [],
        "oa_responses":         [],
        "behavioral_transcript":[],
        "composite_score":       0.0,
        "score_breakdown":       None,  # type: ignore[assignment]
        "rank":                  0,
        "shortlisted":           False,
        "calendly_link":         "",
        "zoom_url":              "",
        "invite_sent":           False,
        "invite_status":         "PENDING",
        "graph2_complete":       False,
    }
    try:
        await run_behavioral_oa(state)
        logger.info("[jobs] agent2 complete job=%s candidate=%s", job_id, candidate_id)
    except Exception as exc:
        logger.error("[jobs] agent2 failed job=%s candidate=%s: %s", job_id, candidate_id, exc)


# ── Self-hosted scheduling ────────────────────────────────────────────────────

@router.get("/schedule/{candidate_id}", status_code=200)
async def get_schedule_info(candidate_id: str):
    """
    Public endpoint — return interview context for the scheduling page.
    Uses a collection-group lookup so only the candidate_id is needed.
    """
    candidate = find_candidate_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Scheduling link not found or expired")

    job_id = candidate.get("job_id", "")
    job    = get_job(job_id) or {}

    return {
        "candidate_id":   candidate_id,
        "candidate_name": candidate.get("name", ""),
        "job_title":      job.get("title", ""),
        "job_team":       job.get("team", ""),
        "job_locations":  job.get("locations", []),
        "already_confirmed": bool(candidate.get("interview_slot_confirmed")),
        "confirmed_slot":    candidate.get("interview_slot"),
    }


@router.post("/schedule/{candidate_id}/confirm", status_code=200)
async def confirm_schedule(candidate_id: str, payload: dict, background_tasks: BackgroundTasks):
    """
    Candidate confirms their preferred interview slot.
    Payload: { slot: "ISO datetime string", timezone: "America/New_York" }
    """
    candidate = find_candidate_by_id(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Scheduling link not found")

    if candidate.get("interview_slot_confirmed"):
        raise HTTPException(status_code=409, detail="Slot already confirmed")

    slot     = str(payload.get("slot", "")).strip()
    timezone = str(payload.get("timezone", "UTC")).strip()
    if not slot:
        raise HTTPException(status_code=400, detail="slot is required")

    job_id = candidate.get("job_id", "")
    job    = get_job(job_id) or {}

    # Create Google Calendar event + Meet link (async, runs before DB write)
    meet_url = ""
    try:
        from app.agents.agent3 import create_google_calendar_event
        meet_url = await create_google_calendar_event(
            candidate_name=candidate.get("name", ""),
            candidate_email=candidate.get("email", ""),
            role_title=job.get("title", "the role"),
            slot_iso=slot,
            slot_timezone=timezone,
        )
    except Exception as exc:
        logger.warning("[jobs] Google Calendar event creation failed: %s", exc)

    update_candidate(job_id, candidate_id, {
        "interview_slot":           slot,
        "interview_timezone":       timezone,
        "interview_slot_confirmed": True,
        "pipeline_stage":           "INTERVIEW_SCHEDULED",
        **({"zoom_url": meet_url} if meet_url else {}),
    })

    logger.info("[jobs] interview slot confirmed candidate=%s slot=%s meet=%s",
                candidate_id, slot, meet_url or "N/A")

    # Send confirmation email
    from app.services.a6_client import send_interview_confirmation
    background_tasks.add_task(
        send_interview_confirmation,
        candidate_name=candidate.get("name", ""),
        candidate_email=candidate.get("email", ""),
        role_title=job.get("title", "the role"),
        interview_slot=slot,
        zoom_url=meet_url or candidate.get("zoom_url", ""),
        interviewer_name="the hiring team",
    )

    return {"confirmed": True, "slot": slot, "candidate_id": candidate_id,
            "meet_url": meet_url or None}


@router.get("/{job_id}/report")
async def get_job_report(job_id: str):
    """
    Run A7 audit and return salary report + top candidates + audit summary.
    Results are also persisted to Firestore under jobs/{job_id}.audit.
    """
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    logger.info("[jobs] report requested job=%s", job_id)
    audit = await run_audit(job_id)

    job = get_job(job_id) or {}
    salary_report = job.get("salary_report")

    all_candidates = get_candidates(job_id)
    top_candidates = [
        c for c in all_candidates
        if c.get("shortlisted")
    ][:5]

    return {
        "job_id":         job_id,
        "salary_report":  salary_report,
        "top_candidates": top_candidates,
        "audit":          audit,
    }


@router.post(
    "/{job_id}/candidates/{candidate_id}/interview-feedback",
    response_model=InterviewFeedbackResponse,
    status_code=200,
)
async def submit_interview_feedback(
    job_id: str,
    candidate_id: str,
    payload: InterviewFeedbackRequest,
    background_tasks: BackgroundTasks,
):
    if not get_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if not get_candidate(job_id, candidate_id):
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id} not found")

    logger.info(
        "[jobs] interview feedback job=%s candidate=%s round=%d/%d result=%s",
        job_id,
        candidate_id,
        payload.round_number,
        payload.total_rounds,
        payload.result,
    )

    background_tasks.add_task(
        _run_interview_pipeline,
        job_id=job_id,
        candidate_id=candidate_id,
        round_number=payload.round_number,
        result=payload.result,
        feedback=payload.feedback,
        total_rounds=payload.total_rounds,
        interviewer_name=payload.interviewer_name,
        technical_score=payload.technical_score,
        communication_score=payload.communication_score,
        problem_solving_score=payload.problem_solving_score,
        cultural_fit_score=payload.cultural_fit_score,
        recommendation=payload.recommendation,
    )

    is_rejected = payload.result == "REJECTED"
    is_last_round = payload.round_number >= payload.total_rounds
    if is_rejected:
        next_action = "REJECTED"
        message = f"Rejected at round {payload.round_number}. Notifications are being prepared."
    elif is_last_round:
        next_action = "MARKET_ANALYSIS"
        message = f"All {payload.total_rounds} rounds passed. Market analysis is in progress."
    else:
        next_action = "SCHEDULE_NEXT_ROUND"
        message = (
            f"Round {payload.round_number} passed. "
            f"Round {payload.round_number + 1} is being scheduled."
        )

    return InterviewFeedbackResponse(
        candidate_id=candidate_id,
        round_number=payload.round_number,
        result=payload.result,
        next_action=next_action,
        message=message,
    )


async def _run_interview_pipeline(
    job_id: str,
    candidate_id: str,
    round_number: int,
    result: str,
    feedback: str,
    total_rounds: int,
    interviewer_name: str | None,
    technical_score: int | None = None,
    communication_score: int | None = None,
    problem_solving_score: int | None = None,
    cultural_fit_score: int | None = None,
    recommendation: str | None = None,
) -> None:
    # Upload structured feedback to Firebase Storage before running the pipeline
    if any(v is not None for v in [technical_score, communication_score, problem_solving_score, cultural_fit_score]):
        from app.services.firestore_service import upload_interview_feedback as _upload_fb
        feedback_data = {
            "round_number": round_number,
            "result": result,
            "feedback": feedback,
            "interviewer_name": interviewer_name,
            "technical_score": technical_score,
            "communication_score": communication_score,
            "problem_solving_score": problem_solving_score,
            "cultural_fit_score": cultural_fit_score,
            "recommendation": recommendation,
        }
        try:
            _upload_fb(job_id, candidate_id, round_number, feedback_data)
            logger.info("[jobs] feedback uploaded to storage job=%s cid=%s round=%d", job_id, candidate_id, round_number)
        except Exception as exc:
            logger.warning("[jobs] feedback storage upload failed: %s", exc)

    try:
        final_state = await run_interview_round_pipeline(
            job_id=job_id,
            candidate_id=candidate_id,
            round_number=round_number,
            result=result,
            feedback=feedback,
            total_rounds=total_rounds,
            interviewer_name=interviewer_name,
        )
        logger.info(
            "[jobs] interview pipeline done job=%s candidate=%s round=%d action=%s",
            job_id,
            candidate_id,
            round_number,
            final_state.get("next_action"),
        )
    except Exception as exc:
        logger.error(
            "[jobs] interview pipeline failed job=%s candidate=%s round=%d error=%s",
            job_id,
            candidate_id,
            round_number,
            exc,
        )


@router.post("/referrals", status_code=201)
async def submit_referral(payload: ReferralRequest):
    """
    Accept a referral submission. Creates a candidate stub marked as referred.
    The referring candidate's scoring bonus is handled by A5 during screening.
    """
    job = get_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {payload.job_id} not found")

    candidate_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db_doc = {
        "candidate_id": candidate_id,
        "job_id": payload.job_id,
        "name": payload.candidate_name,
        "email": payload.candidate_email,
        "github_url": "",
        "linkedin_url": None,
        "location": "",
        "pipeline_stage": "REFERRED",
        "source": "referral",
        "is_referred": True,
        "referrer_name": payload.referrer_name,
        "referrer_email": payload.referrer_email,
        "referral_note": payload.note,
        "source_score": 0.0,
        "source_signals": {},
        "github_signals": {"languages": [], "top_repos": [], "commit_frequency": "", "profile_summary": "", "followers": 0},
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
    from app.services.firestore_service import get_db
    get_db().collection("jobs").document(payload.job_id).collection("candidates").document(candidate_id).set(db_doc)
    logger.info("[jobs] referral submitted job=%s referree=%s referrer=%s",
                payload.job_id, payload.candidate_email, payload.referrer_email)
    return {"candidate_id": candidate_id, "message": "Referral received. We'll be in touch shortly."}