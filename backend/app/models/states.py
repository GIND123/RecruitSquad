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
    reschedule_count: int
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
    """
    Minimum fields an interviewer portal submits per round.

    The portal drill-down provides job_id + candidate_id.
    The interviewer fills in round_result, round_feedback, and optionally
    completed_at.  round_number and total_rounds are auto-derived by
    update_interview_scorecard from the candidate's current Firestore state
    so the caller never has to track them manually.
    """
    job_id: str
    candidate_id: str
    round_result: str       # "SELECTED" | "REJECTED"
    round_feedback: str     # free-text interviewer notes
    next_action: str
    salary_report: SalaryReport | None
    email_to_candidate: dict | None
    email_to_manager: dict | None


class InterviewRoundState(InterviewRoundStateBase, total=False):
    # Auto-derived if omitted — caller does not need to set these
    round_number: int           # derived: candidate.current_round + 1
    total_rounds: int           # derived: candidate.total_rounds → job.total_interview_rounds → 3
    # Interviewer portal optional fields
    completed_at: datetime      # when the interview was completed; defaults to now()
    interviewer_name: str | None
    interviewer_id: str | None  # optional portal user ID
    confirmations_sent: bool
    report_sent_to_manager: bool