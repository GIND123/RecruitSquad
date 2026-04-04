"""Tests for A4 Market Analyst (salary benchmarks, percentile, budget warning)."""
from __future__ import annotations

import asyncio

import pytest

from app.agents.agent4_market_analyst import run_market_analyst


class DummyJobStore:
    def __init__(self):
        self.updated = {}

    def get_job(self, job_id: str):
        return {
            "job_id": job_id,
            "title": "Senior Backend Engineer",
            "locations": ["New York"],
            "tech_stack": ["Python", "FastAPI", "PostgreSQL"],
            "experience_min": 5,
            "experience_max": 8,
            "budget_min": 120000.0,
            "budget_max": 160000.0,
        }

    def update_job(self, job_id: str, data: dict):
        self.updated[job_id] = data


def test_run_market_analyst(monkeypatch):
    store = DummyJobStore()

    monkeypatch.setattr("app.agents.agent4_market_analyst.get_job", store.get_job)
    monkeypatch.setattr("app.agents.agent4_market_analyst.update_job", store.update_job)

    state = {
        "job_id": "job123",
        "shortlisted_candidates": [],
        "confirmed_slots": [],
        "salary_report": None,
        "confirmations_sent": False,
        "report_sent_to_manager": False,
        "graph3_complete": False,
    }

    updated_state = asyncio.run(run_market_analyst(state))

    assert updated_state["graph3_complete"] is True
    assert updated_state["salary_report"] is not None
    assert updated_state["salary_report"].job_id == "job123"
    assert "salary_report" in store.updated["job123"]


def test_check_budget_warning():
    from app.agents.agent4_market_analyst import check_budget_warning

    assert check_budget_warning(100000, 120000) is True
    assert check_budget_warning(130000, 120000) is False