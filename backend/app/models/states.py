from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from app.models.schemas import (
    CandidateProfile,
    OAQuestion,
    OAResponse,
    SalaryReport,
    ScoreBreakdown,
)


# ── Graph 1 State — Sourcing ─────────────────────────────────────────────────

class SourcingState(TypedDict):
    job_id: str
    jd_text: str
    tech_stack: list[str]
    experience_range: tuple[int, int]
    locations: list[str]
    sourced_candidates: list[CandidateProfile]
    outreach_sent: bool
    graph1_complete: bool


# ── Graph 2 State — Screening ────────────────────────────────────────────────

class ScreeningState(TypedDict):
    job_id: str
    candidate_id: str
    jd_text: str
    oa_questions: list[OAQuestion]
    oa_responses: list[OAResponse]
    behavioral_transcript: list[dict]
    composite_score: float
    score_breakdown: ScoreBreakdown
    rank: int
    shortlisted: bool
    calendly_link: str
    zoom_url: str
    invite_sent: bool
    invite_status: str
    graph2_complete: bool


# ── Graph 3 State — Coordination ─────────────────────────────────────────────

class InterviewSlot(TypedDict):
    candidate_id: str
    slot: datetime
    zoom_url: str
    calendly_event_id: str


class CoordinationState(TypedDict):
    job_id: str
    shortlisted_candidates: list[str]
    confirmed_slots: list[InterviewSlot]
    salary_report: SalaryReport
    confirmations_sent: bool
    report_sent_to_manager: bool
    graph3_complete: bool
