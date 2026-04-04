from __future__ import annotations

import logging
from typing import Any

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    END = "__END__"
    StateGraph = None

from app.agents.agent4 import run_market_analyst
from app.agents.agent5 import update_interview_scorecard
from app.models.states import InterviewRoundState

logger = logging.getLogger(__name__)


class _FallbackGraph4:
    async def ainvoke(self, state: InterviewRoundState) -> InterviewRoundState:
        state = update_interview_scorecard(state)
        action = _route_after_scorecard(state)
        if action == "SCHEDULE_NEXT_ROUND":
            state = _placeholder_schedule_next(state)
            state = _placeholder_notify_both(state)
            return state
        if action == "MARKET_ANALYSIS":
            state = await run_market_analyst(state)
            state = _placeholder_notify_manager(state)
            return state
        state = _placeholder_notify_both(state)
        return state


def build_graph4() -> Any:
    if StateGraph is None:
        logger.info("Graph4 using internal fallback runner because langgraph is unavailable")
        return _FallbackGraph4()

    graph = StateGraph(InterviewRoundState)
    graph.add_node("update_scorecard", update_interview_scorecard)
    graph.add_node("market_analyst", run_market_analyst)
    graph.add_node("schedule_next", _placeholder_schedule_next)
    graph.add_node("notify_both", _placeholder_notify_both)
    graph.add_node("notify_manager", _placeholder_notify_manager)

    graph.set_entry_point("update_scorecard")
    graph.add_conditional_edges(
        "update_scorecard",
        _route_after_scorecard,
        {
            "SCHEDULE_NEXT_ROUND": "schedule_next",
            "MARKET_ANALYSIS": "market_analyst",
            "REJECTED": "notify_both",
        },
    )
    graph.add_edge("schedule_next", "notify_both")
    graph.add_edge("notify_both", END)
    graph.add_edge("market_analyst", "notify_manager")
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


def _placeholder_schedule_next(state: InterviewRoundState) -> InterviewRoundState:
    logger.info(
        "Graph4 schedule_next placeholder for candidate=%s next_round=%s",
        state.get("candidate_id"),
        (state.get("round_number") or 0) + 1,
    )
    return state


def _placeholder_notify_both(state: InterviewRoundState) -> InterviewRoundState:
    logger.info(
        "Graph4 notify_both placeholder for candidate=%s action=%s",
        state.get("candidate_id"),
        state.get("next_action"),
    )
    return {**state, "confirmations_sent": True}


def _placeholder_notify_manager(state: InterviewRoundState) -> InterviewRoundState:
    logger.info(
        "Graph4 notify_manager placeholder for job=%s candidate=%s",
        state.get("job_id"),
        state.get("candidate_id"),
    )
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
    return await pipeline.ainvoke(initial_state)