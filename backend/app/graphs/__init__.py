from __future__ import annotations

import logging
from typing import Any

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = "__END__"
    StateGraph = None

from app.agents.agent5 import update_interview_scorecard
from app.models.states import InterviewRoundState

logger = logging.getLogger(__name__)


class _FallbackGraph4:
    async def ainvoke(self, state: InterviewRoundState) -> InterviewRoundState:
        state = await update_interview_scorecard(state)
        action = _route_after_scorecard(state)
        if action == "SCHEDULE_NEXT_ROUND":
            state = await _node_schedule_next(state)
            state = await _node_notify_both(state)
            return state
        if action == "MARKET_ANALYSIS":
            state = await _node_notify_manager(state)
            return state
        state = await _node_notify_both(state)
        return state


def build_graph4() -> Any:
    if StateGraph is None:
        logger.info("Graph4 using internal fallback runner because langgraph is unavailable")
        return _FallbackGraph4()

    graph = StateGraph(InterviewRoundState)
    graph.add_node("update_scorecard", update_interview_scorecard)
    graph.add_node("schedule_next", _node_schedule_next)
    graph.add_node("notify_both",   _node_notify_both)
    graph.add_node("notify_manager", _node_notify_manager)

    graph.set_entry_point("update_scorecard")
    graph.add_conditional_edges(
        "update_scorecard",
        _route_after_scorecard,
        {
            "SCHEDULE_NEXT_ROUND": "schedule_next",
            "MARKET_ANALYSIS": "notify_manager",
            "REJECTED": "notify_both",
        },
    )
    graph.add_edge("schedule_next", "notify_both")
    graph.add_edge("notify_both", END)
    graph.add_edge("notify_manager", END)

    return graph.compile()


def _route_after_scorecard(state: InterviewRoundState) -> str:
    action = state.get("next_action", "REJECTED")
    logger.info(
        "Graph4 routing job=%s candidate=%s action=%s",
        state.get("job_id"),
        state.get("candidate_id"),
        action,
    )
    return action


async def _node_schedule_next(state: InterviewRoundState) -> InterviewRoundState:
    """
    Create Calendly + Zoom links for the next interview round via A3, then
    append the booking URL to the candidate-facing email payload in state so
    _node_notify_both can dispatch a single complete email.
    """
    from app.agents.agent3 import create_calendly_link, create_zoom_meeting
    from app.services.firestore_service import get_candidate, get_job, update_candidate

    job_id       = state.get("job_id", "")
    candidate_id = state.get("candidate_id", "")
    next_round   = (state.get("round_number") or 0) + 1

    candidate      = get_candidate(job_id, candidate_id) or {}
    job            = get_job(job_id) or {}
    candidate_name = candidate.get("name", "Candidate")
    role_title     = job.get("title", "the role")

    logger.info("Graph4 schedule_next: job=%s candidate=%s next_round=%d",
                job_id, candidate_id, next_round)

    calendly_link = await create_calendly_link(
        candidate_name=candidate_name,
        candidate_id=candidate_id,
        role_title=role_title,
    )
    zoom_url = await create_zoom_meeting(
        candidate_name=candidate_name,
        role_title=role_title,
    )

    update_candidate(job_id, candidate_id, {
        "calendly_link":    calendly_link,
        "zoom_url":         zoom_url,
        "pipeline_stage":   "INTERVIEW_SCHEDULED",
        "interview_status": "PENDING",
    })

    # Append the actual links to the pre-built candidate email payload
    email = dict(state.get("email_to_candidate") or {})
    if email:
        suffix = (
            f"\n\nBook your Round {next_round} slot:\n"
            f"  Schedule: {calendly_link}\n"
            f"  Zoom:     {zoom_url}\n"
        )
        email["body"] = email.get("body", "") + suffix

    logger.info("Graph4 schedule_next done | calendly=%s zoom=%s", calendly_link, zoom_url)
    return {**state, "email_to_candidate": email or state.get("email_to_candidate")}


async def _node_notify_both(state: InterviewRoundState) -> InterviewRoundState:
    """Dispatch candidate + manager emails built by A5's update_interview_scorecard."""
    import os
    from app.services.a6_client import send_generic_email

    manager_email = os.environ.get("MANAGER_EMAIL", "")

    email_c = state.get("email_to_candidate")
    email_m = state.get("email_to_manager")

    if email_c:
        to      = str(email_c.get("to", ""))
        subject = str(email_c.get("subject", ""))
        body    = str(email_c.get("body", ""))
        if to and subject:
            await send_generic_email(to=to, subject=subject, body=body)
            logger.info("Graph4 notify_both: candidate email sent to=%s subject=%r", to, subject)

    if email_m and manager_email:
        subject = str(email_m.get("subject", ""))
        body    = str(email_m.get("body", ""))
        if subject:
            await send_generic_email(to=manager_email, subject=subject, body=body)
            logger.info("Graph4 notify_both: manager email sent subject=%r", subject)

    logger.info("Graph4 notify_both done | job=%s candidate=%s action=%s",
                state.get("job_id"), state.get("candidate_id"), state.get("next_action"))
    return {**state, "confirmations_sent": True}


async def _node_notify_manager(state: InterviewRoundState) -> InterviewRoundState:
    """Dispatch manager-only email (all interview rounds passed — market analysis triggered)."""
    import os
    from app.services.a6_client import send_generic_email

    manager_email = os.environ.get("MANAGER_EMAIL", "")
    email_m       = state.get("email_to_manager")

    if email_m and manager_email:
        subject = str(email_m.get("subject", ""))
        body    = str(email_m.get("body", ""))
        if subject:
            await send_generic_email(to=manager_email, subject=subject, body=body)
            logger.info("Graph4 notify_manager: email sent subject=%r", subject)
    elif not manager_email:
        logger.warning("Graph4 notify_manager: MANAGER_EMAIL not set — skipping")

    logger.info("Graph4 notify_manager done | job=%s candidate=%s",
                state.get("job_id"), state.get("candidate_id"))
    return {**state, "report_sent_to_manager": True}


async def run_interview_round_pipeline(
    job_id: str,
    candidate_id: str,
    round_number: int,
    result: str,
    feedback: str,
    total_rounds: int,
    interviewer_name: str | None = None,
) -> InterviewRoundState:
    initial_state: InterviewRoundState = {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "round_number": round_number,
        "round_result": result,
        "round_feedback": feedback,
        "interviewer_name": interviewer_name,
        "total_rounds": total_rounds,
        "next_action": "",
        "salary_report": None,
        "email_to_candidate": None,
        "email_to_manager": None,
        "confirmations_sent": False,
        "report_sent_to_manager": False,
    }

    pipeline = build_graph4()
    final_state = await pipeline.ainvoke(initial_state)

    # If the final interview round passed, kick off Graph 3 (coordination + market)
    if final_state.get("next_action") == "MARKET_ANALYSIS":
        try:
            from app.graphs.graph3 import run_coordination_pipeline
            logger.info("Graph4 → triggering Graph3 for job=%s candidate=%s", job_id, candidate_id)
            await run_coordination_pipeline(job_id=job_id, candidate_id=candidate_id)
        except Exception as exc:
            logger.error("Graph4 → Graph3 handoff failed job=%s: %s", job_id, exc)

    return final_state


# ── Re-export all graph public runners ───────────────────────────────────────
from app.graphs.graph1 import run_sourcing_pipeline     # noqa: E402  F401
from app.graphs.graph2 import run_screening_pipeline    # noqa: E402  F401
from app.graphs.graph3 import run_coordination_pipeline  # noqa: E402  F401

__all__ = [
    "run_interview_round_pipeline",
    "run_sourcing_pipeline",
    "run_screening_pipeline",
    "run_coordination_pipeline",
    "build_graph4",
]