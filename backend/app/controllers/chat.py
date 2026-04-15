"""
Chat controller — Behavioral Interview
=======================================
Exposes the A2 conduct_behavioral_chat function over HTTP so the
candidate-facing React page can drive a live conversational interview.

Authentication: oa_token (UUID in the URL) acts as the bearer credential.
No separate login is required — candidates access via the link in their
OA invite email.

Endpoints:
  GET  /api/chat/{oa_token}              — resolve token, return context
  POST /api/chat/{oa_token}/message      — send one message, receive AI reply
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.agent2 import conduct_behavioral_chat
from app.services.firestore_service import (
    find_candidate_by_oa_token,
    get_candidate,
    get_job,
    update_candidate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Keywords that signal the AI has finished all questions
_COMPLETION_SIGNALS = [
    "session is complete",
    "interview is complete",
    "all questions have been",
    "that concludes",
    "thank you for completing",
    "you have completed",
    "interview session is now complete",
]


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatContext(BaseModel):
    candidate_name: str
    job_title: str
    question_count: int


class ChatMessageRequest(BaseModel):
    message: str
    history: list[dict]   # [{"role": "assistant"|"user", "content": str}, ...]


class ChatMessageResponse(BaseModel):
    reply: str
    is_complete: bool
    candidate_name: str
    job_title: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_token(oa_token: str) -> tuple[str, str]:
    """Return (job_id, candidate_id) for a valid oa_token, or raise 404."""
    match = find_candidate_by_oa_token(oa_token)
    if not match:
        raise HTTPException(status_code=404, detail="Invalid or expired interview token")
    return match["job_id"], match["candidate_id"]


def _is_complete(reply: str) -> bool:
    lower = reply.lower()
    return any(signal in lower for signal in _COMPLETION_SIGNALS)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/{oa_token}", response_model=ChatContext)
async def get_chat_context(oa_token: str):
    """Return candidate name, job title, and number of behavioral questions."""
    job_id, candidate_id = _resolve_token(oa_token)
    candidate = get_candidate(job_id, candidate_id) or {}
    job       = get_job(job_id) or {}

    questions: list = candidate.get("behavioral_questions") or []
    return ChatContext(
        candidate_name=candidate.get("name", "Candidate"),
        job_title=job.get("title", "the role"),
        question_count=len(questions),
    )


@router.post("/{oa_token}/message", response_model=ChatMessageResponse)
async def send_chat_message(oa_token: str, payload: ChatMessageRequest):
    """
    Process one candidate message and return the AI interviewer's reply.

    On first call, send message="" with history=[] to receive the opening
    question. Subsequent calls include the full prior history so the AI
    maintains context.

    The behavioral transcript is persisted to Firestore after every exchange
    so partial sessions are recoverable.
    """
    job_id, candidate_id = _resolve_token(oa_token)

    candidate      = get_candidate(job_id, candidate_id) or {}
    job            = get_job(job_id) or {}
    candidate_name = candidate.get("name", "Candidate")
    job_title      = job.get("title", "the role")

    logger.info("[chat] message | job=%s candidate=%s history_len=%d",
                job_id, candidate_id, len(payload.history))

    # Determine question count before the LLM call so we can set completion accurately
    behavioral_questions: list = candidate.get("behavioral_questions") or []
    question_count = len(behavioral_questions)

    # Count how many questions the candidate has already answered (user turns in history)
    # plus the current message (if non-empty) as the latest answer
    answers_given = sum(1 for m in payload.history if m.get("role") == "user")
    if payload.message:
        answers_given += 1

    reply = await conduct_behavioral_chat(
        candidate_id=candidate_id,
        job_id=job_id,
        candidate_message=payload.message,
        history=payload.history,
    )

    # Persist updated transcript to Firestore (incremental — safe to replay)
    new_transcript: list[dict] = list(payload.history)
    if payload.message:
        new_transcript.append({"role": "user", "content": payload.message})
    new_transcript.append({"role": "assistant", "content": reply})

    # Use answer count as the source of truth; text matching is a fallback
    complete = (question_count > 0 and answers_given >= question_count) or _is_complete(reply)
    update_candidate(job_id, candidate_id, {
        "behavioral_transcript":       new_transcript,
        "behavioral_chat_in_progress": not complete,
        **({"behavioral_complete": True} if complete else {}),
    })

    if complete:
        logger.info("[chat] session complete | job=%s candidate=%s", job_id, candidate_id)
        # Re-trigger Graph 2 so composite is re-scored with the real behavioral score
        # and the interview scheduling invite is sent (if OA already passed).
        import asyncio
        from app.graphs import run_screening_pipeline
        asyncio.create_task(run_screening_pipeline(job_id=job_id, candidate_id=candidate_id))

    return ChatMessageResponse(
        reply=reply,
        is_complete=complete,
        candidate_name=candidate_name,
        job_title=job_title,
    )
