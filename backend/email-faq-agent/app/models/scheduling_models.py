from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class InterviewerInfo(BaseModel):
    name: str
    calendly_link: str


# ── Internal structured types (used by send_interview_invite) ──────────────────

class ScheduleRequest(BaseModel):
    candidate_name: str
    candidate_email: EmailStr
    interviewer_user_ids: list[str] = Field(..., min_length=1)
    subject: str = "Interview Invitation"
    custom_message: Optional[str] = None


class ScheduleResponse(BaseModel):
    status: str
    message: str
    candidate_email: str
    interviewers: list[InterviewerInfo]
    links_sent: list[str]


# ── Agentic endpoint types ─────────────────────────────────────────────────────

class AIScheduleRequest(BaseModel):
    task: str = Field(..., description="Plain English scheduling instruction")


class AIScheduleResponse(BaseModel):
    status: str                  # "sent" | "failed"
    summary: str                 # what the agent did or why it failed
    candidate_email: str = ""
    interviewers: list[InterviewerInfo] = []
    links_sent: list[str] = []
