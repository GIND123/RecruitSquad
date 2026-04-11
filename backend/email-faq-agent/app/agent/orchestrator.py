import json
from typing import Optional
from app.models.email_models import (
    AgentTaskRequest,
    AgentTaskResponse,
    SendMode,
    Priority,
)
from app.services.email_service import send_email
from app.services.template_service import (
    resolve_template,
    validate_template_data,
    render_template,
    render_text_fallback,
)
from app.services.user_store import get_user_by_id
from app.kafka.producer import publish_email_job
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _estimate_payload_size(request: AgentTaskRequest) -> int:
    return len(json.dumps(request.model_dump()))


def _decide_send_mode(request: AgentTaskRequest) -> SendMode:
    if request.send_mode != SendMode.auto:
        return request.send_mode
    if request.priority == Priority.high:
        return SendMode.immediate
    payload_size = _estimate_payload_size(request)
    if payload_size > settings.auto_queue_threshold_bytes:
        return SendMode.queued
    return SendMode.immediate


async def handle_email_task(request: AgentTaskRequest) -> AgentTaskResponse:
    # Resolve recipient from user_id if provided
    recipient = str(request.recipient) if request.recipient else None
    template_data = dict(request.template_data or {})

    if request.user_id:
        user = get_user_by_id(request.user_id)
        if not user:
            return AgentTaskResponse(
                status="rejected",
                action_taken="user_not_found",
                message=f"No user found with id={request.user_id}",
                recipient=recipient or "",
            )
        recipient = user["email"]
        # auto-inject name and email into template_data if not already set
        template_data.setdefault("name", user["name"])
        template_data.setdefault("email", user["email"])

    if not recipient:
        return AgentTaskResponse(
            status="rejected",
            action_taken="validation_failed",
            message="Either recipient or user_id is required",
            recipient="",
        )

    logger.info(f"Agent task: email_type={request.email_type} recipient={recipient}")

    template_name = resolve_template(request.email_type, request.template_name)

    if template_name:
        missing = validate_template_data(template_name, template_data)
        if missing:
            logger.warning(f"Validation failed for template={template_name}, missing={missing}")
            return AgentTaskResponse(
                status="rejected",
                action_taken="validation_failed",
                message=f"Missing required template fields: {', '.join(missing)}",
                recipient=recipient,
            )

    subject = request.subject or f"[{request.email_type.replace('_', ' ').title()}]"
    mode = _decide_send_mode(request)

    if mode == SendMode.immediate:
        body_html = None
        body_text = None
        if template_name and template_data:
            body_html = render_template(template_name, template_data)
            body_text = render_text_fallback(template_name, template_data)
        try:
            await send_email(
                to=recipient,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            return AgentTaskResponse(
                status="success",
                action_taken="sent_immediately",
                message="Email sent successfully",
                recipient=recipient,
            )
        except Exception as exc:
            logger.error(f"Immediate send failed: {exc}")
            return AgentTaskResponse(
                status="error",
                action_taken="send_failed",
                message=str(exc),
                recipient=recipient,
            )
    else:
        job_id = await publish_email_job(
            to=recipient,
            subject=subject,
            template_name=template_name,
            template_data=template_data if template_data else None,
            priority=request.priority,
        )
        return AgentTaskResponse(
            status="success",
            action_taken="enqueued",
            message=f"Email job enqueued with id={job_id}",
            job_id=job_id,
            recipient=recipient,
        )