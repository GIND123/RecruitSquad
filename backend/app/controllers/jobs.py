from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.agent1.sourcing_hunter import run_sourcing_hunter
from app.graphs import run_interview_round_pipeline
from app.models.schemas import (
    InterviewFeedbackRequest,
    InterviewFeedbackResponse,
    JobCreateRequest,
    JobResponse,
)
from app.models.states import SourcingState
from app.services.firestore_service import get_candidate, get_candidates, get_job, update_job

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
        "status": "PENDING",
        "candidate_count": 0,
        "created_at": now,
    }
    update_job(job_id, job_doc)
    logger.info("[jobs] created job=%s title=%r", job_id, payload.title)

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
    try:
        await run_sourcing_hunter(state)
        update_job(state["job_id"], {"status": "SOURCED"})
        logger.info("[jobs] agent1 complete job=%s", state["job_id"])
    except Exception as exc:
        logger.error("[jobs] agent1 failed job=%s: %s", state["job_id"], exc)
        update_job(state["job_id"], {"status": "FAILED", "error": str(exc)})


@router.get("/{job_id}/candidates")
async def list_candidates(job_id: str):
    """Return all sourced candidates for a job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "candidates": get_candidates(job_id)}


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
) -> None:
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