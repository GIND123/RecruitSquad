"""Tests for Graph 4 interview routing."""
from __future__ import annotations

import asyncio

from app.graphs import run_interview_round_pipeline


def test_run_interview_round_pipeline_market_analysis(monkeypatch):
    def fake_update_interview_scorecard(state):
        return {
            **state,
            "next_action": "MARKET_ANALYSIS",
            "email_to_candidate": None,
            "email_to_manager": {"type": "ALL_ROUNDS_DONE_MANAGER"},
            "salary_report": None,
        }

    async def fake_run_market_analyst(state):
        return {
            **state,
            "salary_report": {"p50": 150000},
            "email_to_manager": {"type": "SALARY_REPORT_MANAGER"},
        }

    monkeypatch.setattr("app.graphs.update_interview_scorecard", fake_update_interview_scorecard)
    monkeypatch.setattr("app.graphs.run_market_analyst", fake_run_market_analyst)

    result = asyncio.run(
        run_interview_round_pipeline(
            job_id="job123",
            candidate_id="cand1",
            round_number=2,
            result="SELECTED",
            feedback="Strong final round.",
            total_rounds=2,
            interviewer_name="Manager A",
        )
    )

    assert result["next_action"] == "MARKET_ANALYSIS"
    assert result["report_sent_to_manager"] is True
    assert result["email_to_manager"]["type"] == "SALARY_REPORT_MANAGER"
    assert result["salary_report"]["p50"] == 150000


def test_run_interview_round_pipeline_schedule_next(monkeypatch):
    def fake_update_interview_scorecard(state):
        return {
            **state,
            "next_action": "SCHEDULE_NEXT_ROUND",
            "email_to_candidate": {"type": "ROUND_SELECTED_CANDIDATE"},
            "email_to_manager": {"type": "ROUND_SELECTED_MANAGER"},
            "salary_report": None,
        }

    monkeypatch.setattr("app.graphs.update_interview_scorecard", fake_update_interview_scorecard)

    result = asyncio.run(
        run_interview_round_pipeline(
            job_id="job123",
            candidate_id="cand1",
            round_number=1,
            result="SELECTED",
            feedback="Pass to round 2.",
            total_rounds=3,
            interviewer_name="Manager A",
        )
    )

    assert result["next_action"] == "SCHEDULE_NEXT_ROUND"
    assert result["confirmations_sent"] is True
    assert result["email_to_candidate"]["type"] == "ROUND_SELECTED_CANDIDATE"