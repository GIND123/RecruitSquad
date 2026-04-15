"""
Graph 2 — Screening Pipeline
==============================
Triggered per-candidate once they submit the OA (via POST /api/oa/{token}/submit).
Also callable manually from the manager dashboard.

Flow:
    behavioral_oa (A2)         ← evaluate submitted OA responses & reset transcript
          │
    scoring_engine (A5)        ← compute composite score, rerank job-wide, shortlist
          │
    ┌─────┴──────────┐
    │  shortlisted?  │
    │   NO → notify_rejected (A6) → END
    │   YES ↓
    coordinator (A3-stub)      ← generate Calendly + Zoom links
          │
    email_invite (A6)          ← send interview invite to candidate + manager
          │
    ┌─────┴────────────────────┐
    │  invite_status?          │
    │  RESCHEDULED → coordinator (loop back, max 3 times)
    │  else         → END

State: ScreeningState
A3 is implemented as a stub (Calendly/Zoom not yet integrated); it produces
placeholder links that are still persisted and emailed so the full flow runs.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__END__"
    StateGraph = None
    _LANGGRAPH_AVAILABLE = False

from app.agents.agent2 import evaluate_oa_responses, run_behavioral_oa
from app.agents.agent5 import run_scoring_engine
from app.models.schemas import OAQuestion, OAResponse
from app.models.states import ScreeningState
from app.services.firestore_service import get_candidate, get_job, update_candidate

logger = logging.getLogger(__name__)

_MAX_RESCHEDULE_LOOPS = 3


# ══════════════════════════════════════════════════════════════════════════════
# Graph nodes
# ══════════════════════════════════════════════════════════════════════════════

async def _node_behavioral_oa(state: ScreeningState) -> ScreeningState:
    """
    Score the submitted OA using A2's LLM evaluator, then persist the score
    via A5's update_scorecard_after_oa helper.
    """
    from app.agents.agent5 import update_scorecard_after_oa

    job_id       = state["job_id"]
    candidate_id = state["candidate_id"]

    logger.info("[Graph2] node: behavioral_oa | job=%s candidate=%s", job_id, candidate_id)

    # Fetch persisted questions + responses from Firestore
    candidate = get_candidate(job_id, candidate_id) or {}
    raw_questions = candidate.get("oa_questions") or []
    raw_responses = candidate.get("oa_responses") or []

    questions = [OAQuestion(**q) for q in raw_questions]
    responses = [OAResponse(**r) for r in raw_responses]

    oa_score = evaluate_oa_responses(questions, responses)
    logger.info("[Graph2] OA score=%.1f | candidate=%s", oa_score, candidate_id)

    # Persist via A5 (sets oa_score, oa_passed, pipeline_stage)
    update_scorecard_after_oa(job_id, candidate_id, oa_score)

    # Re-fetch so downstream nodes use fresh Firestore data
    candidate     = get_candidate(job_id, candidate_id) or {}
    jd_text       = str((get_job(job_id) or {}).get("role_description") or "")
    behavioral_tx = candidate.get("behavioral_transcript") or []

    return {
        **state,
        "jd_text":              jd_text,
        "oa_questions":         questions,
        "oa_responses":         responses,
        "behavioral_transcript": behavioral_tx,
    }


async def _node_scoring_engine(state: ScreeningState) -> ScreeningState:
    logger.info("[Graph2] node: scoring_engine | job=%s candidate=%s",
                state["job_id"], state["candidate_id"])
    return await run_scoring_engine(state)


async def _node_coordinator(state: ScreeningState) -> ScreeningState:
    """
    A3: create interview scheduling link.
    The Google Meet link is generated later when the candidate confirms their slot.
    """
    from app.agents.agent3 import create_calendly_link

    job_id       = state["job_id"]
    candidate_id = state["candidate_id"]
    candidate    = get_candidate(job_id, candidate_id) or {}
    job          = get_job(job_id) or {}

    candidate_name = candidate.get("name", "Candidate")
    role_title     = job.get("title", "the role")

    logger.info("[Graph2] node: coordinator | candidate=%s", candidate_id)

    calendly_link = await create_calendly_link(
        candidate_name=candidate_name,
        candidate_id=candidate_id,
        role_title=role_title,
    )

    update_candidate(job_id, candidate_id, {
        "calendly_link":    calendly_link,
        "zoom_url":         "",
        "pipeline_stage":   "INTERVIEW_SCHEDULED",
        "interview_status": "PENDING",
    })

    logger.info("[Graph2] coordinator done | candidate=%s schedule_link=%s",
                candidate_id, calendly_link)

    return {
        **state,
        "calendly_link":    calendly_link,
        "zoom_url":         "",
        "invite_status":    "PENDING",
        "reschedule_count": state.get("reschedule_count", 0) + 1,
    }


async def _node_email_invite(state: ScreeningState) -> ScreeningState:
    """Send interview invite to candidate and notify manager via A6."""
    from app.services.a6_client import send_interview_invite

    job_id       = state["job_id"]
    candidate_id = state["candidate_id"]
    candidate    = get_candidate(job_id, candidate_id) or {}
    job          = get_job(job_id) or {}

    name       = candidate.get("name", "Candidate")
    email      = candidate.get("email", "")
    role_title = job.get("title", "the role")

    logger.info("[Graph2] node: email_invite | candidate=%s email=%s", candidate_id, email)

    if email:
        await send_interview_invite(
            candidate_name=name,
            candidate_email=email,
            role_title=role_title,
            calendly_link=state.get("calendly_link", ""),
            zoom_url=state.get("zoom_url", ""),
            interviewer_ids=[],   # A3 will populate when implemented
        )

    update_candidate(job_id, candidate_id, {"invite_sent": True})
    return {**state, "invite_sent": True}


async def _node_await_behavioral(state: ScreeningState) -> ScreeningState:
    """
    OA passed but behavioral interview not yet complete.
    Hold here — chat.py re-triggers the pipeline once behavioral finishes.
    """
    job_id       = state["job_id"]
    candidate_id = state["candidate_id"]
    logger.info("[Graph2] node: await_behavioral | candidate=%s — holding for behavioral completion",
                candidate_id)
    update_candidate(job_id, candidate_id, {"pipeline_stage": "AWAITING_BEHAVIORAL"})
    return {**state, "graph2_complete": True}


async def _node_notify_rejected(state: ScreeningState) -> ScreeningState:
    """Candidate did not score high enough — send rejection email via A6."""
    from app.services.a6_client import send_rejection

    job_id       = state["job_id"]
    candidate_id = state["candidate_id"]
    candidate    = get_candidate(job_id, candidate_id) or {}
    job          = get_job(job_id) or {}

    name       = candidate.get("name", "Candidate")
    email      = candidate.get("email", "")
    role_title = job.get("title", "the role")

    logger.info("[Graph2] node: notify_rejected | candidate=%s", candidate_id)

    update_candidate(job_id, candidate_id, {"pipeline_stage": "REJECTED"})

    if email:
        await send_rejection(
            candidate_name=name,
            candidate_email=email,
            role_title=role_title,
        )

    return {**state, "graph2_complete": True}


# ══════════════════════════════════════════════════════════════════════════════
# Routing functions (conditional edges)
# ══════════════════════════════════════════════════════════════════════════════

def _route_after_scoring(state: ScreeningState) -> str:
    """
    Three-way gate:
      1. OA failed                          → notify_rejected
      2. OA passed, behavioral not done yet → await_behavioral (hold; chat.py re-triggers)
      3. OA passed + behavioral done        → check composite shortlist flag
           shortlisted=True  → coordinator (send interview invite)
           shortlisted=False → notify_rejected
    """
    job_id       = state.get("job_id", "")
    candidate_id = state.get("candidate_id", "?")

    candidate = get_candidate(job_id, candidate_id) or {}
    oa_passed           = bool(candidate.get("oa_passed"))
    behavioral_complete = bool(candidate.get("behavioral_complete"))
    shortlisted         = bool(candidate.get("shortlisted"))

    logger.info(
        "[Graph2] route_after_scoring | candidate=%s oa_passed=%s behavioral_complete=%s shortlisted=%s",
        candidate_id, oa_passed, behavioral_complete, shortlisted,
    )

    if not oa_passed:
        return "notify_rejected"
    if not behavioral_complete:
        return "await_behavioral"
    return "coordinator" if shortlisted else "notify_rejected"


def _route_after_invite(state: ScreeningState) -> str:
    invite_status = str(state.get("invite_status") or "PENDING").upper()
    reschedule_count = int(state.get("reschedule_count", 0))  # type: ignore[arg-type]
    candidate_id = state.get("candidate_id", "?")

    if invite_status == "RESCHEDULED" and reschedule_count < _MAX_RESCHEDULE_LOOPS:
        logger.info("[Graph2] route_after_invite | candidate=%s → loop back (reschedule #%d)",
                    candidate_id, reschedule_count + 1)
        return "coordinator"

    logger.info("[Graph2] route_after_invite | candidate=%s status=%s → END", candidate_id, invite_status)
    return END


# ══════════════════════════════════════════════════════════════════════════════
# Fallback runner
# ══════════════════════════════════════════════════════════════════════════════

class _FallbackGraph2:
    async def ainvoke(self, state: ScreeningState) -> ScreeningState:
        state    = await _node_behavioral_oa(state)
        state    = await _node_scoring_engine(state)
        decision = _route_after_scoring(state)
        if decision == "notify_rejected":
            return await _node_notify_rejected(state)
        if decision == "await_behavioral":
            return await _node_await_behavioral(state)
        # Both OA and behavioral complete, shortlisted — proceed to interview invite
        state = await _node_coordinator(state)
        state = await _node_email_invite(state)
        state["graph2_complete"] = True  # type: ignore[assignment]
        return state


# ══════════════════════════════════════════════════════════════════════════════
# Graph builder
# ══════════════════════════════════════════════════════════════════════════════

def build_graph2() -> Any:
    if not _LANGGRAPH_AVAILABLE or StateGraph is None:
        logger.info("[Graph2] LangGraph unavailable — using fallback runner")
        return _FallbackGraph2()

    graph = StateGraph(ScreeningState)

    graph.add_node("behavioral_oa",     _node_behavioral_oa)
    graph.add_node("scoring_engine",    _node_scoring_engine)
    graph.add_node("await_behavioral",  _node_await_behavioral)
    graph.add_node("coordinator",       _node_coordinator)
    graph.add_node("email_invite",      _node_email_invite)
    graph.add_node("notify_rejected",   _node_notify_rejected)

    graph.set_entry_point("behavioral_oa")
    graph.add_edge("behavioral_oa", "scoring_engine")

    # Three-way branch after scoring:
    #   OA failed                       → notify_rejected
    #   OA passed, behavioral pending   → await_behavioral (hold)
    #   OA + behavioral passed          → coordinator (send invite)
    graph.add_conditional_edges(
        "scoring_engine",
        _route_after_scoring,
        {
            "coordinator":      "coordinator",
            "await_behavioral": "await_behavioral",
            "notify_rejected":  "notify_rejected",
        },
    )

    graph.add_edge("await_behavioral", END)

    graph.add_edge("coordinator", "email_invite")

    # Bidirectional A3 ↔ A6: loop back to coordinator if candidate reschedules
    graph.add_conditional_edges(
        "email_invite",
        _route_after_invite,
        {
            "coordinator": "coordinator",
            END:           END,
        },
    )

    graph.add_edge("notify_rejected", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════════════════════
# Public runner
# ══════════════════════════════════════════════════════════════════════════════

async def run_screening_pipeline(
    job_id: str,
    candidate_id: str,
) -> ScreeningState:
    """
    Entry point for the screening pipeline.
    Called from POST /api/oa/{token}/submit (oa_controller — to be implemented).
    """
    candidate = get_candidate(job_id, candidate_id) or {}
    job       = get_job(job_id)         or {}

    initial_state: ScreeningState = {
        "job_id":               job_id,
        "candidate_id":         candidate_id,
        "jd_text":              str(job.get("role_description") or ""),
        "oa_questions":         [],   # hydrated in _node_behavioral_oa
        "oa_responses":         [],   # hydrated in _node_behavioral_oa
        "behavioral_transcript": candidate.get("behavioral_transcript") or [],
        "composite_score":       0.0,
        "score_breakdown":       None,  # type: ignore[assignment]
        "rank":                  0,
        "shortlisted":           False,
        "calendly_link":         "",
        "zoom_url":              "",
        "invite_sent":           False,
        "invite_status":         "PENDING",
        "reschedule_count":      0,
        "graph2_complete":       False,
    }

    pipeline = build_graph2()
    final    = await pipeline.ainvoke(initial_state)
    logger.info("[Graph2] pipeline done | job=%s candidate=%s shortlisted=%s",
                job_id, candidate_id, final.get("shortlisted"))
    return final
