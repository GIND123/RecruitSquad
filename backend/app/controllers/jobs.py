"""
Jobs controller — /api/jobs

POST /api/jobs
  Creates a job document in Firestore and kicks off Agent 1
  (sourcing hunter) as a FastAPI BackgroundTask.

GET /api/jobs/{job_id}/candidates
  Returns the sourced candidate list for a job.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.agents.agent1.sourcing_hunter import run_sourcing_hunter
from app.models.schemas import JobCreateRequest, JobResponse
from app.models.states import SourcingState
from app.services.firestore_service import get_job, get_candidates, update_job

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ── POST /api/jobs ────────────────────────────────────────────────────────────

@router.post("", response_model=JobResponse, status_code=201)
async def create_job(payload: JobCreateRequest, background_tasks: BackgroundTasks):
    """Create a job and trigger Agent 1 sourcing in the background."""
    job_id = str(uuid.uuid4())
    now    = datetime.now(timezone.utc)

    job_doc = {
        "job_id":         job_id,
        "title":          payload.title,
        "role_description": payload.role_description,
        "headcount":      payload.headcount,
        "budget_min":     payload.budget_min,
        "budget_max":     payload.budget_max,
        "locations":      payload.locations,
        "experience_min": payload.experience_min,
        "experience_max": payload.experience_max,
        "team":           payload.team,
        "status":         "PENDING",
        "candidate_count": 0,
        "created_at":     now,
    }
    update_job(job_id, job_doc)
    logger.info("[jobs] created job=%s title=%r", job_id, payload.title)

    initial_state: SourcingState = {
        "job_id":             job_id,
        "jd_text":            payload.role_description,
        "tech_stack":         [],
        "experience_range":   (payload.experience_min, payload.experience_max),
        "locations":          payload.locations,
        "sourced_candidates": [],
        "outreach_sent":      False,
        "graph1_complete":    False,
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
    except Exception as e:
        logger.error("[jobs] agent1 failed job=%s: %s", state["job_id"], e)
        update_job(state["job_id"], {"status": "FAILED", "error": str(e)})


# ── GET /api/jobs/{job_id}/candidates ────────────────────────────────────────

@router.get("/{job_id}/candidates")
async def list_candidates(job_id: str):
    """Return all sourced candidates for a job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "candidates": get_candidates(job_id)}
