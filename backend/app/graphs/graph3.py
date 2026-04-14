"""
Graph 3 — Coordination & Market Pipeline
==========================================
Triggered from Graph 4 (post last interview round) when next_action == "MARKET_ANALYSIS".

Flow:
    scoring_final (A5)             ← final ranking across all shortlisted candidates
          │
    ┌─────┴───────────────────┐
    │                         │
    market_analyst (A4)    coordinator_final (A3-stub)
    (runs concurrently         ← send interview confirmations to all shortlisted
     as sequential nodes)
    │                         │
    email_salary_report (A6)  email_confirmations (A6)
    (manager only)
    │                         │
    └─────────────┬───────────┘
                 END

Because LangGraph 0.2 sequential graphs don't natively run two parallel branches,
we model this as two independent chains that merge at END:
    scoring_final → market_analyst → email_salary_report → coordinator_final → email_confirmations → END

State: CoordinationState
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

from app.agents.agent4 import run_market_analyst
from app.agents.agent5 import run_scoring_ranking
from app.models.states import CoordinationState
from app.services.firestore_service import get_candidate, get_candidates, get_job, update_candidate, update_job

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Graph nodes
# ══════════════════════════════════════════════════════════════════════════════

def _node_scoring_final(state: CoordinationState) -> CoordinationState:
    """
    A5: run final ranking across all fully-screened candidates.
    Updates composite_score, rank, shortlisted in Firestore for each candidate.
    """
    job_id = state["job_id"]
    logger.info("[Graph3] node: scoring_final | job=%s", job_id)
    result = run_scoring_ranking(state)
    shortlisted_ids: list[str] = result.get("shortlisted_candidates", [])
    logger.info("[Graph3] scoring_final done | shortlisted=%d", len(shortlisted_ids))
    return {**state, "shortlisted_candidates": shortlisted_ids}


async def _node_market_analyst(state: CoordinationState) -> CoordinationState:
    """A4: run salary market analysis for the job."""
    logger.info("[Graph3] node: market_analyst | job=%s", state["job_id"])
    return await run_market_analyst(state)


async def _node_email_salary_report(state: CoordinationState) -> CoordinationState:
    """A6: forward A4's salary report email to the hiring manager."""
    from app.services.a6_client import send_salary_report_to_manager

    job_id = state["job_id"]
    logger.info("[Graph3] node: email_salary_report | job=%s", job_id)

    email_payload = state.get("email_to_manager")
    if email_payload:
        await send_salary_report_to_manager(email_payload)
    else:
        logger.warning("[Graph3] email_salary_report: no email_to_manager in state — skipping")

    update_job(job_id, {"salary_report_emailed": True})
    return {**state, "report_sent_to_manager": True}


async def _node_coordinator_final(state: CoordinationState) -> CoordinationState:
    """
    A3: create/refresh scheduling links for every shortlisted candidate.
    Reuses an existing link if Graph 2 already created one.
    Google Meet links are generated later when each candidate confirms their slot.
    """
    from app.agents.agent3 import create_calendly_link

    job_id = state["job_id"]
    job    = get_job(job_id) or {}
    role_title = str(job.get("title") or "the role")
    shortlisted_ids: list[str] = state.get("shortlisted_candidates") or []

    logger.info("[Graph3] node: coordinator_final | job=%s shortlisted=%d",
                job_id, len(shortlisted_ids))

    confirmed_slots = []

    for candidate_id in shortlisted_ids:
        candidate = get_candidate(job_id, candidate_id) or {}
        candidate_name = candidate.get("name", "Candidate")

        # Reuse Graph 2's link if already set, otherwise create a fresh one
        existing_calendly = candidate.get("calendly_link", "")
        calendly_link = (
            existing_calendly
            if existing_calendly and "/schedule/" not in existing_calendly
            else await create_calendly_link(
                candidate_name=candidate_name,
                candidate_id=candidate_id,
                role_title=role_title,
            )
        )

        update_candidate(job_id, candidate_id, {
            "calendly_link":    calendly_link,
            "pipeline_stage":   "INTERVIEW_SCHEDULED",
            "interview_status": "PENDING",
        })

        confirmed_slots.append({
            "candidate_id":      candidate_id,
            "slot":              None,   # filled when candidate confirms their slot
            "meet_url":          "",    # filled after slot confirmation via Google Calendar
            "calendly_event_id": "",
        })

        logger.info("[Graph3] coordinator_final candidate=%s schedule_link=%s",
                    candidate_id, calendly_link)

    return {**state, "confirmed_slots": confirmed_slots}  # type: ignore[return-value]


async def _node_email_confirmations(state: CoordinationState) -> CoordinationState:
    """A6: send interview invite emails to all shortlisted candidates."""
    from app.services.a6_client import send_interview_invite, send_shortlist_notification

    job_id      = state["job_id"]
    job         = get_job(job_id) or {}
    role_title  = str(job.get("title") or "the role")
    shortlisted = state.get("shortlisted_candidates") or []

    logger.info("[Graph3] node: email_confirmations | job=%s candidates=%d",
                job_id, len(shortlisted))

    sent = 0
    for candidate_id in shortlisted:
        candidate = get_candidate(job_id, candidate_id) or {}
        name       = candidate.get("name", "Candidate")
        email      = candidate.get("email", "")
        cal_link   = candidate.get("calendly_link", "")
        zoom       = candidate.get("zoom_url", "")

        if not email:
            continue

        ok = await send_interview_invite(
            candidate_name=name,
            candidate_email=email,
            role_title=role_title,
            calendly_link=cal_link,
            zoom_url=zoom,
            interviewer_ids=[],
        )
        if ok:
            sent += 1
            update_candidate(job_id, candidate_id, {"invite_sent": True})

    logger.info("[Graph3] email_confirmations done | sent=%d/%d", sent, len(shortlisted))
    update_job(job_id, {"status": "SCHEDULING"})

    return {**state, "confirmations_sent": True, "graph3_complete": True}


# ══════════════════════════════════════════════════════════════════════════════
# Fallback runner
# ══════════════════════════════════════════════════════════════════════════════

class _FallbackGraph3:
    async def ainvoke(self, state: CoordinationState) -> CoordinationState:
        state = _node_scoring_final(state)
        state = await _node_market_analyst(state)
        state = await _node_email_salary_report(state)
        state = await _node_coordinator_final(state)
        state = await _node_email_confirmations(state)
        return state


# ══════════════════════════════════════════════════════════════════════════════
# Graph builder
# ══════════════════════════════════════════════════════════════════════════════

def build_graph3() -> Any:
    if not _LANGGRAPH_AVAILABLE or StateGraph is None:
        logger.info("[Graph3] LangGraph unavailable — using fallback runner")
        return _FallbackGraph3()

    graph = StateGraph(CoordinationState)

    graph.add_node("scoring_final",         _node_scoring_final)
    graph.add_node("market_analyst",        _node_market_analyst)
    graph.add_node("email_salary_report",   _node_email_salary_report)
    graph.add_node("coordinator_final",     _node_coordinator_final)
    graph.add_node("email_confirmations",   _node_email_confirmations)

    graph.set_entry_point("scoring_final")

    # Chain: final scores → market analysis → email report to manager
    graph.add_edge("scoring_final",       "market_analyst")
    graph.add_edge("market_analyst",      "email_salary_report")

    # Chain: market report sent → confirm interviews → emails to candidates
    graph.add_edge("email_salary_report", "coordinator_final")
    graph.add_edge("coordinator_final",   "email_confirmations")
    graph.add_edge("email_confirmations", END)

    return graph.compile()


# ══════════════════════════════════════════════════════════════════════════════
# Public runner
# ══════════════════════════════════════════════════════════════════════════════

async def run_coordination_pipeline(
    job_id: str,
    candidate_id: str | None = None,
) -> CoordinationState:
    """
    Entry point for the coordination pipeline.
    Called from Graph 4 (run_interview_round_pipeline) when last round passes,
    or manually from the manager dashboard.
    """
    job = get_job(job_id) or {}

    # Collect all shortlisted candidate IDs as starting input
    shortlisted_ids = [
        c["candidate_id"]
        for c in get_candidates(job_id)
        if c.get("shortlisted") and c.get("candidate_id")
    ]

    initial_state: CoordinationState = {
        "job_id":                  job_id,
        "candidate_id":            candidate_id or "",     # type: ignore[typeddict-item]
        "shortlisted_candidates":  shortlisted_ids,
        "confirmed_slots":         [],
        "salary_report":           None,
        "confirmations_sent":      False,
        "report_sent_to_manager":  False,
        "graph3_complete":         False,
        "email_to_manager":        None,     # type: ignore[typeddict-item]
        "email_to_candidate":      None,     # type: ignore[typeddict-item]
    }

    pipeline = build_graph3()
    final    = await pipeline.ainvoke(initial_state)
    logger.info("[Graph3] pipeline done | job=%s shortlisted=%d complete=%s",
                job_id, len(shortlisted_ids), final.get("graph3_complete"))
    return final
