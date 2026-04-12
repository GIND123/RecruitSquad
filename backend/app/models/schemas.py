from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class JobCreateRequest(BaseModel):
    title: str
    role_description: str
    headcount: int
    budget_min: float
    budget_max: float
    locations: list[str]
    experience_min: int
    experience_max: int
    team: str


class JobResponse(BaseModel):
    job_id: str
    title: str
    status: str
    headcount: int
    candidate_count: int
    created_at: datetime


class ScoreBreakdown(BaseModel):
    source_fit: float
    oa_score: float
    behavioral_score: float


class CandidateResponse(BaseModel):
    candidate_id: str
    name: str
    email: str
    github_url: str
    linkedin_url: str | None = None
    pipeline_stage: str
    composite_score: float | None = None
    rank: int | None = None
    source_score: float
    score_breakdown: ScoreBreakdown | None = None
    interview_slot: datetime | None = None
    shortlisted: bool


class StageUpdateRequest(BaseModel):
    stage: Literal[
        "SOURCED",
        "OA_SENT",
        "BEHAVIORAL_COMPLETE",
        "SCORED",
        "SHORTLISTED",
        "INTERVIEW_SCHEDULED",
        "INTERVIEW_DONE",
        "OFFERED",
        "HIRED",
        "REJECTED",
    ]
    reason: str | None = None


class OAQuestion(BaseModel):
    question_id: str
    question_text: str
    type: Literal["MCQ", "CODING", "TEXT"]
    options: list[str] | None = None
    time_limit_minutes: int | None = None


class OAResponse(BaseModel):
    question_id: str
    answer: str


class OASubmission(BaseModel):
    candidate_id: str
    oa_token: str
    responses: list[OAResponse]


class ChatMessage(BaseModel):
    content: str


class ChatReply(BaseModel):
    content: str
    timestamp: datetime


class ReferralRequest(BaseModel):
    job_id: str
    referrer_name: str
    referrer_email: EmailStr
    candidate_name: str
    candidate_email: EmailStr
    note: str | None = None


class GithubProfile(BaseModel):
    login: str
    name: str
    email: str | None = None
    location: str | None = None
    bio: str | None = None
    top_repos: list[str] = []
    languages: list[str] = []
    public_repos: int = 0
    followers: int = 0
    github_url: str
    account_created_at: datetime | None = None


class LinkedInProfile(BaseModel):
    name: str
    linkedin_url: str
    headline: str | None = None
    location: str | None = None
    snippet: str | None = None


class CandidateProfile(BaseModel):
    """Unified candidate profile combining GitHub and LinkedIn signals."""

    name: str
    email: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    location: str | None = None
    bio: str | None = None
    headline: str | None = None
    top_repos: list[str] = []
    languages: list[str] = []
    public_repos: int = 0
    followers: int = 0
    source: Literal["github", "linkedin", "both"] = "github"


class SalaryReport(BaseModel):
    job_id: str
    location: str
    role_title: str
    p25: float
    p50: float
    p75: float
    p90: float
    budget_min: float
    budget_max: float
    budget_warning: bool
    data_sources: list[str]
    analysis_summary: str | None = None
    generated_at: datetime


class InterviewRound(BaseModel):
    round_number: int
    result: Literal["SELECTED", "REJECTED", "PENDING"]
    feedback: str
    interviewer_name: str | None = None
    scheduled_at: datetime | None = None
    completed_at: datetime | None = None


class InterviewFeedbackRequest(BaseModel):
    round_number: int
    result: Literal["SELECTED", "REJECTED"]
    feedback: str
    interviewer_name: str | None = None
    total_rounds: int = 1


class InterviewFeedbackResponse(BaseModel):
    candidate_id: str
    round_number: int
    result: str
    next_action: Literal[
        "SCHEDULE_NEXT_ROUND",
        "MARKET_ANALYSIS",
        "REJECTED",
    ]
    message: str