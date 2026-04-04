from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from app.models.schemas import CandidateProfile, OAQuestion, OAResponse, SalaryReport, ScoreBreakdown


class SourcingState(TypedDict):
    job_id: str
    jd_text: str
    tech_stack: list[str]
    experience_range: tuple[int, int]
    locations: list[str]
    sourced_candidates: list[CandidateProfile]
    outreach_sent: bool
    graph1_complete: bool


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


class InterviewSlot(TypedDict):
    candidate_id: str
    slot: datetime
    zoom_url: str
    calendly_event_id: str


class CoordinationStateBase(TypedDict):
    job_id: str
    shortlisted_candidates: list[str]
    confirmed_slots: list[InterviewSlot]
    salary_report: SalaryReport | None
    confirmations_sent: bool
    report_sent_to_manager: bool
    graph3_complete: bool


class CoordinationState(CoordinationStateBase, total=False):
    candidate_id: str
    email_to_manager: dict
    email_to_candidate: dict | None


class InterviewRoundStateBase(TypedDict):
    job_id: str
    candidate_id: str
    round_number: int
    round_result: str
    round_feedback: str
    total_rounds: int
    next_action: str
    salary_report: SalaryReport | None
    email_to_candidate: dict | None
    email_to_manager: dict | None


class InterviewRoundState(InterviewRoundStateBase, total=False):
    interviewer_name: str | None
    confirmations_sent: bool
    report_sent_to_manager: bool