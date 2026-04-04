"""Tests for A5 scoring, ranking, and interview routing."""
from __future__ import annotations

import asyncio

import pytest

from app.agents.agent5 import (
    compute_composite_score,
    compute_source_scores,
    recompute_rankings,
    run_scoring_engine,
    run_scoring_ranking,
    update_interview_scorecard,
    update_scorecard_after_behavioral,
    update_scorecard_after_oa,
    evaluate_behavioral_transcript,
)


def test_compute_composite_score():
    composite, breakdown = compute_composite_score(80, 90, 70)
    assert isinstance(composite, float)
    assert composite == pytest.approx(80 * 0.2 + 90 * 0.4 + 70 * 0.4)
    assert breakdown.source_fit == 80


def test_evaluate_behavioral_transcript():
    transcript = [
        {"content": "I have 5 years of Python and FastAPI experience."},
        {"content": "I worked on distributed systems and scaling."},
    ]
    score = evaluate_behavioral_transcript(transcript, "Python FastAPI distributed systems")
    assert 0 <= score <= 100


def test_recompute_rankings(monkeypatch):
    updated = {}

    def fake_get_candidates(job_id):
        return [
            {"candidate_id": "c1", "composite_score": 75},
            {"candidate_id": "c2", "composite_score": 90},
        ]

    def fake_update_candidate(job_id, candidate_id, data):
        updated[candidate_id] = data

    monkeypatch.setattr("app.agents.agent5.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5.update_candidate", fake_update_candidate)

    asyncio.run(recompute_rankings("job123"))

    assert updated["c2"]["rank"] == 1
    assert updated["c1"]["rank"] == 2


def test_compute_source_scores_job_id(monkeypatch):
    updated = {}

    def fake_get_candidates(job_id):
        return [
            {
                "candidate_id": "c1",
                "source": "github",
                "github_signals": {
                    "followers": 50,
                    "top_repos": ["a", "b", "c"],
                    "languages": ["Python", "SQL"],
                },
            }
        ]

    def fake_update_candidate(job_id, candidate_id, data):
        updated[candidate_id] = data

    monkeypatch.setattr("app.agents.agent5.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5.update_candidate", fake_update_candidate)

    compute_source_scores("job123")

    assert "source_score" in updated["c1"]
    assert "source_signals" in updated["c1"]


def test_update_scorecard_after_behavioral_rejects_experience(monkeypatch):
    updates = {}

    monkeypatch.setattr(
        "app.agents.agent5.get_job",
        lambda job_id: {
            "experience_min": 4,
            "experience_max": 7,
            "budget_max": 150000,
            "locations": ["New York"],
        },
    )
    monkeypatch.setattr(
        "app.agents.agent5.update_candidate",
        lambda job_id, candidate_id, data: updates.update(data),
    )

    result = update_scorecard_after_behavioral(
        "job123",
        "cand1",
        behavioral_transcript=[{"content": "hello"}],
        salary_expected=120000,
        years_experience=2,
        willing_to_relocate=False,
        candidate_location="Boston",
    )

    assert result["proceed"] is False
    assert updates["pipeline_stage"] == "EXPERIENCE_REJECTED"
    assert updates["experience_passed"] is False


def test_update_scorecard_after_behavioral_passes(monkeypatch):
    updates = {}

    monkeypatch.setattr(
        "app.agents.agent5.get_job",
        lambda job_id: {
            "experience_min": 3,
            "experience_max": 7,
            "budget_max": 150000,
            "locations": ["Remote", "New York"],
        },
    )
    monkeypatch.setattr(
        "app.agents.agent5.update_candidate",
        lambda job_id, candidate_id, data: updates.update(data),
    )

    result = update_scorecard_after_behavioral(
        "job123",
        "cand1",
        behavioral_transcript=[{"content": "hello"}],
        salary_expected=120000,
        years_experience=5,
        willing_to_relocate=False,
        candidate_location="Boston",
        behavioral_summary="Strong communication",
        behavioral_score=88,
    )

    assert result == {"proceed": True, "rejection_reason": None}
    assert updates["pipeline_stage"] == "BEHAVIORAL_COMPLETE"
    assert updates["location_passed"] is True
    assert updates["salary_within_budget"] is True


def test_update_scorecard_after_oa(monkeypatch):
    updates = {}
    monkeypatch.setattr(
        "app.agents.agent5.update_candidate",
        lambda job_id, candidate_id, data: updates.update(data),
    )

    failed = update_scorecard_after_oa("job123", "cand1", 65)
    assert failed["proceed"] is False
    assert updates["pipeline_stage"] == "OA_FAILED"

    updates.clear()
    passed = update_scorecard_after_oa("job123", "cand1", 92)
    assert passed["proceed"] is True
    assert updates["pipeline_stage"] == "OA_SENT"
    assert updates["oa_passed"] is True


def test_run_scoring_engine(monkeypatch):
    updated_candidates = {}

    def fake_get_candidate(job_id, candidate_id):
        return {
            "candidate_id": candidate_id,
            "source_score": 60,
            "oa_score": 0,
            "behavioral_score": 0,
        }

    def fake_get_candidates(job_id):
        return [
            {"candidate_id": "c2", "composite_score": 95},
            {"candidate_id": "c1", "composite_score": 90},
        ]

    def fake_update_candidate(job_id, candidate_id, data):
        updated_candidates.setdefault(candidate_id, {}).update(data)

    monkeypatch.setattr("app.agents.agent5.get_candidate", fake_get_candidate)
    monkeypatch.setattr("app.agents.agent5.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5.update_candidate", fake_update_candidate)

    state = {
        "job_id": "job123",
        "candidate_id": "c1",
        "jd_text": "Python FastAPI distributed systems",
        "oa_questions": [{"question_id": "q1"}],
        "oa_responses": [{"question_id": "q1", "answer": "Yes"}],
        "behavioral_transcript": [{"content": "I built scalable systems with Python."}],
    }

    updated_state = asyncio.run(run_scoring_engine(state))
    assert updated_state["composite_score"] >= 0
    assert updated_state["shortlisted"] in (True, False)
    assert "score_breakdown" in updated_candidates["c1"]


def test_run_scoring_ranking_filters_candidates_and_updates_job(monkeypatch):
    candidate_updates = {}
    job_updates = {}

    monkeypatch.setattr("app.agents.agent5.get_job", lambda job_id: {"headcount": 1})
    monkeypatch.setattr(
        "app.agents.agent5.get_candidates",
        lambda job_id: [
            {
                "candidate_id": "c1",
                "experience_passed": True,
                "location_passed": True,
                "salary_within_budget": True,
                "oa_passed": True,
                "behavioral_complete": True,
                "composite_score": 88,
            },
            {
                "candidate_id": "c2",
                "experience_passed": False,
                "location_passed": True,
                "salary_within_budget": True,
                "oa_passed": True,
                "behavioral_complete": True,
                "composite_score": 99,
            },
        ],
    )
    monkeypatch.setattr(
        "app.agents.agent5.update_candidate",
        lambda job_id, candidate_id, data: candidate_updates.setdefault(candidate_id, {}).update(data),
    )
    monkeypatch.setattr(
        "app.agents.agent5.update_job",
        lambda job_id, data: job_updates.update(data),
    )

    result = run_scoring_ranking({"job_id": "job123"})

    assert result["shortlisted_candidates"] == ["c1"]
    assert candidate_updates["c1"]["shortlisted"] is True
    assert candidate_updates["c2"]["shortlisted"] is False
    assert job_updates["status"] == "SCHEDULING"


def test_update_interview_scorecard_routes_to_market_analysis(monkeypatch):
    saved_round = {}
    updated = {}

    monkeypatch.setattr(
        "app.agents.agent5.get_candidate",
        lambda job_id, candidate_id: {
            "candidate_id": candidate_id,
            "name": "Bala Govind",
            "email": "bala@example.com",
        },
    )
    monkeypatch.setattr(
        "app.agents.agent5.save_interview_round",
        lambda **kwargs: saved_round.update(kwargs),
    )
    monkeypatch.setattr(
        "app.agents.agent5.update_candidate",
        lambda job_id, candidate_id, data: updated.update(data),
    )
    monkeypatch.setattr(
        "app.agents.agent5.get_job",
        lambda job_id: {"title": "Backend Engineer"},
    )

    state = {
        "job_id": "job123",
        "candidate_id": "cand1",
        "round_number": 2,
        "round_result": "SELECTED",
        "round_feedback": "Strong system design round.",
        "interviewer_name": "Manager A",
        "total_rounds": 2,
        "next_action": "",
        "salary_report": None,
        "email_to_candidate": None,
        "email_to_manager": None,
    }

    result = update_interview_scorecard(state)

    assert result["next_action"] == "MARKET_ANALYSIS"
    assert result["email_to_candidate"] is None
    assert result["email_to_manager"]["type"] == "ALL_ROUNDS_DONE_MANAGER"
    assert saved_round["round_number"] == 2
    assert updated["pipeline_stage"] == "INTERVIEW_DONE"