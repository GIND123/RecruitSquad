"""Tests for A4 Market Analyst integration."""
from __future__ import annotations

import asyncio

from app.agents.agent4 import check_budget_warning, run_market_analyst, _synthesize_salary_data


class DummyJobStore:
    def __init__(self):
        self.updated_jobs: dict[str, dict] = {}
        self.updated_candidates: dict[tuple[str, str], dict] = {}

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
        self.updated_jobs[job_id] = data

    def get_candidate(self, job_id: str, candidate_id: str):
        if candidate_id == "cand-1":
            return {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "name": "Bala Govind",
            }
        return None

    def update_candidate(self, job_id: str, candidate_id: str, data: dict):
        self.updated_candidates[(job_id, candidate_id)] = data


def test_run_market_analyst_base_flow(monkeypatch):
    store = DummyJobStore()

    monkeypatch.setattr("app.agents.agent4.get_job", store.get_job)
    monkeypatch.setattr("app.agents.agent4.update_job", store.update_job)
    monkeypatch.setattr("app.agents.agent4._search_salary_data", lambda *args: [])
    monkeypatch.setattr(
        "app.agents.agent4._synthesize_salary_data",
        lambda *args: {
            "p25": 135000,
            "p50": 150000,
            "p75": 168000,
            "p90": 185000,
            "data_sources": ["levels.fyi", "glassdoor.com"],
            "analysis_summary": "Budget is near the market median.",
        },
    )

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
    assert updated_state["salary_report"].analysis_summary == "Budget is near the market median."
    assert updated_state["email_to_manager"]["type"] == "SALARY_REPORT_MANAGER"
    assert updated_state["email_to_candidate"] is None
    assert "salary_report" in store.updated_jobs["job123"]


def test_run_market_analyst_updates_candidate_when_present(monkeypatch):
    store = DummyJobStore()

    monkeypatch.setattr("app.agents.agent4.get_job", store.get_job)
    monkeypatch.setattr("app.agents.agent4.update_job", store.update_job)
    monkeypatch.setattr("app.agents.agent4.get_candidate", store.get_candidate)
    monkeypatch.setattr("app.agents.agent4.update_candidate", store.update_candidate)
    monkeypatch.setattr(
        "app.agents.agent4._search_salary_data",
        lambda *args: [{"link": "https://www.glassdoor.com/Salaries/test"}],
    )
    monkeypatch.setattr(
        "app.agents.agent4._synthesize_salary_data",
        lambda *args: {
            "p25": 170000,
            "p50": 182000,
            "p75": 195000,
            "p90": 210000,
            "data_sources": ["glassdoor.com"],
            "analysis_summary": "Budget falls below entry market pay.",
        },
    )

    state = {
        "job_id": "job123",
        "candidate_id": "cand-1",
        "shortlisted_candidates": [],
        "confirmed_slots": [],
        "salary_report": None,
        "confirmations_sent": False,
        "report_sent_to_manager": False,
        "graph3_complete": False,
    }

    updated_state = asyncio.run(run_market_analyst(state))

    assert updated_state["salary_report"].budget_warning is True
    assert updated_state["email_to_manager"]["budget_warning"] is True
    assert "Bala Govind" in updated_state["email_to_manager"]["subject"]
    assert ("job123", "cand-1") in store.updated_candidates
    assert "salary_report" in store.updated_candidates[("job123", "cand-1")]


def test_synthesize_salary_data_uses_fallback_when_gemini_unavailable(monkeypatch):
    fallback_data = {
        "p25": 100000,
        "p50": 120000,
        "p75": 145000,
        "p90": 170000,
        "data_sources": ["heuristic_fallback"],
        "analysis_summary": "Fallback summary.",
    }

    monkeypatch.setattr("app.agents.agent4._get_gemini_model", lambda: None)

    assert _synthesize_salary_data(
        "Backend Engineer",
        "Remote",
        90000.0,
        120000.0,
        [],
        fallback_data,
    ) == fallback_data


def test_check_budget_warning():
    assert check_budget_warning(100000, 120000) is True
    assert check_budget_warning(130000, 120000) is False
    assert check_budget_warning(0, 120000) is False