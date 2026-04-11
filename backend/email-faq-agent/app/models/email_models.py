from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, Any
from enum import Enum


class SendMode(str, Enum):
    auto = "auto"
    immediate = "immediate"
    queued = "queued"


class Priority(str, Enum):
    high = "high"
    normal = "normal"
    low = "low"


class EmailRequest(BaseModel):
    to: EmailStr
    subject: str
    body_text: Optional[str] = None
    template_name: Optional[str] = None
    template_data: Optional[dict[str, Any]] = None


class EnqueueRequest(EmailRequest):
    priority: Priority = Priority.normal


class AgentTaskRequest(BaseModel):
    email_type: str
    recipient: Optional[EmailStr] = None
    user_id: Optional[str] = None          # look up from users.json
    subject: Optional[str] = None
    template_name: Optional[str] = None
    template_data: Optional[dict[str, Any]] = None
    priority: Priority = Priority.normal
    send_mode: SendMode = SendMode.auto


class EmailJob(BaseModel):
    job_id: str
    to: str
    subject: str
    body_text: Optional[str] = None
    template_name: Optional[str] = None
    template_data: Optional[dict[str, Any]] = None
    retry_count: int = 0
    priority: Priority = Priority.normal


class SendEmailResponse(BaseModel):
    status: str
    message: str
    recipient: str


class EnqueueEmailResponse(BaseModel):
    status: str
    job_id: str
    topic: str


class AgentTaskResponse(BaseModel):
    status: str
    action_taken: str
    message: str
    job_id: Optional[str] = None
    recipient: str


class TemplateInfo(BaseModel):
    name: str
    required_fields: list[str]
    description: str


class TemplatesResponse(BaseModel):
    templates: list[TemplateInfo]


# ── AI agent models ────────────────────────────────────────────────────────────

class AITaskRequest(BaseModel):
    task: str   # natural language, e.g. "Send a welcome email to User"


class ToolCallRecord(BaseModel):
    tool: str
    input: dict[str, Any]
    result: dict[str, Any]


class AITaskResponse(BaseModel):
    status: str
    summary: str
    actions: list[ToolCallRecord]
    total_steps: int


class FAQRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    email: Optional[str] = None


class FAQResponse(BaseModel):
    answer: str
    user: Optional[dict[str, Any]] = None
