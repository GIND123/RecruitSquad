"""Tests for A5 Scoring & Ranking Engine."""
from __future__ import annotations

import asyncio

import pytest

from app.agents.agent5_scoring_ranking import (
    compute_composite_score,
    evaluate_behavioral_transcript,
    recompute_rankings,
    compute_source_scores,
    run_scoring_engine,
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

    monkeypatch.setattr("app.agents.agent5_scoring_ranking.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5_scoring_ranking.update_candidate", fake_update_candidate)

    asyncio.run(recompute_rankings("job123"))

    assert updated["c2"]["rank"] == 1
    assert updated["c1"]["rank"] == 2


def test_calculate_source_scores(monkeypatch):
    updated = {}

    def fake_get_candidates(job_id):
        return [
            {"candidate_id": "c1", "github_signals": {"followers": 50, "top_repos": ["a", "b", "c"]}},
        ]

    def fake_update_candidate(job_id, candidate_id, data):
        updated[candidate_id] = data

    monkeypatch.setattr("app.agents.agent5_scoring_ranking.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5_scoring_ranking.update_candidate", fake_update_candidate)

    compute_source_scores("job123")

    assert "source_score" in updated["c1"]


def test_run_scoring_engine(monkeypatch):
    candidates_store = {
        "c1": {
            "candidate_id": "c1",
            "source_score": 60,
            "composite_score": 0,
            "rank": 1,
        },
        "c2": {
            "candidate_id": "c2",
            "source_score": 80,
            "composite_score": 0,
            "rank": 2,
        },
    }

    def fake_get_candidates(job_id):
        return [candidates_store["c2"], candidates_store["c1"]]

    updated_candidates = {}

    def fake_update_candidate(job_id, candidate_id, data):
        updated_candidates.setdefault(candidate_id, {}).update(data)

    monkeypatch.setattr("app.agents.agent5_scoring_ranking.get_candidates", fake_get_candidates)
    monkeypatch.setattr("app.agents.agent5_scoring_ranking.update_candidate", fake_update_candidate)

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
