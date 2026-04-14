"""
A6 HTTP Client
==============
Sends emails via one of two paths (checked in order):

  1. DIRECT SMTP  — used when SMTP_USER + SMTP_PASS are set.
                    Sends to ALL recipients using Gmail (or any SMTP server).
  2. EMAIL AGENT  — falls back to the email-faq-agent microservice at
                    EMAIL_AGENT_URL when SMTP credentials are absent.

Configuration (env vars):
    SMTP_HOST       smtp.gmail.com
    SMTP_PORT       465
    SMTP_USER       alice.ai.hr.agent@gmail.com
    SMTP_PASS       (Gmail app password — set via Secret Manager / .env, no default)
    FROM_EMAIL      same as SMTP_USER
    EMAIL_AGENT_URL http://localhost:8001     (fallback microservice)

All functions are fire-and-forget:
  - Log on failure, do NOT raise, so graph execution continues.
  - Return True on success, False on failure.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_EMAIL_AGENT_URL = os.environ.get("EMAIL_AGENT_URL", "http://localhost:8001")
_TIMEOUT = 10.0   # seconds

# ── SMTP credentials (baked-in defaults, overridable via env vars) ────────────
# Use `or` so an empty-string env var falls through to the default
_SMTP_HOST  = os.environ.get("SMTP_HOST")  or "smtp.gmail.com"
_SMTP_PORT  = int(os.environ.get("SMTP_PORT") or "465")
_SMTP_USER  = os.environ.get("SMTP_USER")  or "alice.ai.hr.agent@gmail.com"
_SMTP_PASS  = os.environ.get("SMTP_PASS", "")
_FROM_EMAIL = os.environ.get("FROM_EMAIL") or _SMTP_USER

# True when both SMTP creds are present — enables direct-send path
_SMTP_READY = bool(_SMTP_USER and _SMTP_PASS)

# Legacy DRY_RUN flag — if set, skip delivery entirely (useful in CI)
_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() in ("1", "true", "yes")


def _build_body_text(body: dict) -> str:
    """Extract or synthesise a plain-text email body from whichever field is populated."""
    text = body.get("body_text") or ""
    if text:
        return text
    td = body.get("template_data") or {}
    if td.get("job_link"):
        return (
            f"Hi {td.get('candidate_name', '')},\n\n"
            f"We think you'd be a great fit for the {td.get('role_title', '')} role "
            f"at {td.get('company_name', 'RecruitSquad')}.\n\n"
            f"View the full job description and apply here:\n{td['job_link']}\n\n"
            f"Best regards,\n{td.get('company_name', 'RecruitSquad')}"
        )
    if td.get("oa_link"):
        return (
            f"Hi {td.get('candidate_name', '')},\n\n"
            f"You have been invited to apply for the {td.get('role_title', '')} role.\n\n"
            f"Complete your Online Assessment here:\n{td['oa_link']}\n\n"
            f"Best regards,\n{td.get('company_name', 'RecruitSquad')}"
        )
    return str(td) or "(no body)"


def _smtp_send_sync(to: str, subject: str, text: str) -> None:
    """Blocking SMTP send — runs in a thread executor, not on the event loop."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = _FROM_EMAIL
    msg["To"]      = to
    msg.attach(MIMEText(text, "plain"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=ctx) as server:
        server.login(_SMTP_USER, _SMTP_PASS)
        server.sendmail(_FROM_EMAIL, to, msg.as_string())


async def _send_via_smtp(body: dict) -> bool:
    """Send an email via Gmail SMTP SSL (port 465), offloaded to a thread executor."""
    to      = body.get("to", "")
    subject = body.get("subject", "(no subject)")
    text    = _build_body_text(body)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send_sync, to, subject, text)
        logger.info("[A6-client] SMTP sent to=%s subject=%s", to, subject)
        return True
    except Exception as exc:
        logger.error("[A6-client] SMTP send failed to=%s: %s", to, exc)
        return False


async def _send_via_agent(path: str, body: dict) -> bool:
    """POST to the email-faq-agent microservice. Returns True on 2xx."""
    url = f"{_EMAIL_AGENT_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=body)
            if resp.status_code >= 400:
                logger.warning("[A6-client] agent %s → HTTP %d: %s",
                               url, resp.status_code, resp.text[:200])
                return False
            return True
    except Exception as exc:
        logger.warning("[A6-client] agent %s failed: %s", url, exc)
        return False


async def _post(path: str, body: dict) -> bool:
    """
    Dispatch an email using the best available transport:

      DRY_RUN=true  → skip delivery entirely (CI / test mode)
      SMTP ready    → send directly via Gmail SMTP  (preferred)
      fallback      → forward to the email-agent microservice
    """
    if _DRY_RUN:
        logger.info("[A6-client] DRY_RUN — skipped email to=%s subject=%s",
                    body.get("to"), body.get("subject"))
        return True

    if _SMTP_READY:
        return await _send_via_smtp(body)

    return await _send_via_agent(path, body)


# ── High-level helpers ────────────────────────────────────────────────────────

async def send_outreach_email(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    job_link: str,
    company_name: str | None = None,
) -> bool:
    """
    Graph 1: sourcing outreach to a freshly discovered candidate.
    Sends the job posting link so the candidate can apply via the portal.
    The OA invite is sent separately after they submit their application.
    """
    company = company_name or os.environ.get("COMPANY_NAME", "RecruitSquad")
    return await _post("/send-email", {
        "to": candidate_email,
        "subject": f"Exciting opportunity: {role_title} at {company}",
        "template_name": "outreach",
        "template_data": {
            "candidate_name": candidate_name,
            "role_title": role_title,
            "company_name": company,
            "job_link": job_link,
        },
    })


async def send_oa_invite(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    oa_link: str,
    deadline: str = "7 days from now",
    chat_link: str = "",
) -> bool:
    """
    Send the OA + behavioral interview links to a candidate.
    chat_link is the URL to the live behavioral chat page (/oa/{token}/chat).
    """
    body_parts = [
        f"Hi {candidate_name},",
        "",
        f"You have been shortlisted for the {role_title} role. "
        f"Please complete the following steps before {deadline}:",
        "",
        f"1. Online Assessment:\n   {oa_link}",
    ]
    if chat_link:
        body_parts += [
            "",
            f"2. Behavioral Interview (live chat with our AI interviewer):\n   {chat_link}",
        ]
    body_parts += ["", "Best regards,", "The Hiring Team"]

    return await _post("/send-email", {
        "to":        candidate_email,
        "subject":   f"Your Assessment — {role_title}",
        "body_text": "\n".join(body_parts),
    })


async def send_interview_invite(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    calendly_link: str,
    zoom_url: str = "",   # kept for signature compat, no longer used
    interviewer_ids: list[str] = [],
) -> bool:
    """
    Graph 2 / Graph 3: send interview invite with the slot-booking link.
    A Google Meet link is generated and emailed separately once the candidate
    confirms their slot via the scheduling page.
    Falls back to a plain /send-email if the scheduling agent call fails.
    """
    task = (
        f"Schedule an interview for {candidate_name} ({candidate_email}) "
        f"for the {role_title} role. Interviewer IDs: {interviewer_ids}. "
        f"Scheduling link: {calendly_link}."
    )
    ok = await _send_via_agent("/agent/schedule-interview", {"task": task})
    if not ok:
        logger.info("[A6-client] schedule-interview failed, sending plain invite email")
        ok = await _post("/send-email", {
            "to": candidate_email,
            "subject": f"Interview Invitation — {role_title}",
            "body_text": (
                f"Hi {candidate_name},\n\n"
                f"Congratulations! We'd like to invite you for an interview "
                f"for the {role_title} role.\n\n"
                f"Please book your preferred slot here:\n{calendly_link}\n\n"
                f"Once you confirm a slot, you'll receive a Google Meet link "
                f"for the video interview.\n\n"
                f"Best regards,\nThe Hiring Team"
            ),
        })
    return ok


async def send_shortlist_notification(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    next_step: str = "an interview invitation",
) -> bool:
    """Graph 2: notify candidate they passed screening."""
    return await _post("/send-email", {
        "to": candidate_email,
        "subject": f"You've been shortlisted — {role_title}",
        "body_text": (
            f"Hi {candidate_name},\n\n"
            f"Congratulations! You have been shortlisted for the {role_title} role.\n"
            f"You will shortly receive {next_step}.\n\n"
            f"Best regards,\nThe Hiring Team"
        ),
    })


async def send_rejection(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    feedback_note: str = "",
) -> bool:
    """Graphs 2/3: dignified rejection email."""
    body = (
        f"Hi {candidate_name},\n\n"
        f"Thank you for your interest in the {role_title} position and the time "
        f"you invested in our process. After careful consideration, we will not be "
        f"moving forward with your application at this time.\n"
    )
    if feedback_note:
        body += f"\nFeedback: {feedback_note}\n"
    body += "\nWe encourage you to apply for future openings.\n\nBest regards,\nThe Hiring Team"

    return await _post("/send-email", {
        "to": candidate_email,
        "subject": f"Update on your application — {role_title}",
        "body_text": body,
    })


async def send_salary_report_to_manager(email_payload: dict[str, Any]) -> bool:
    """
    Graph 3: forward the salary report email that A4 already built.
    email_payload comes directly from CoordinationState['email_to_manager'].
    """
    subject = email_payload.get("subject", "[RecruitSquad] Salary Report")
    body    = email_payload.get("body", "")
    manager_email = os.environ.get("MANAGER_EMAIL", "")

    if not manager_email:
        logger.warning("[A6-client] MANAGER_EMAIL not set — salary report email skipped")
        return False

    return await _post("/send-email", {
        "to": manager_email,
        "subject": subject,
        "body_text": body,
    })


async def send_application_acknowledgment(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    company_name: str | None = None,
) -> bool:
    """
    Sent immediately when a candidate submits their portal application.
    Confirms receipt and sets expectations about next steps.
    """
    company = company_name or os.environ.get("COMPANY_NAME", "RecruitSquad")
    body = (
        f"Hi {candidate_name},\n\n"
        f"Thank you for applying to the {role_title} position at {company}!\n\n"
        f"We have received your application and our team will review it shortly. "
        f"If your profile is a good match, you will receive an email with an "
        f"Online Assessment and a short behavioral interview to complete.\n\n"
        f"Here's what to expect next:\n"
        f"  1. Application review (typically within 1–2 business days)\n"
        f"  2. Online Assessment + AI behavioral interview (via email)\n"
        f"  3. Interview scheduling (for shortlisted candidates)\n\n"
        f"In the meantime, feel free to reply to this email if you have any questions.\n\n"
        f"Best regards,\n"
        f"The {company} Hiring Team"
    )
    return await _post("/send-email", {
        "to":        candidate_email,
        "subject":   f"We received your application — {role_title} at {company}",
        "body_text": body,
    })


async def send_generic_email(to: str, subject: str, body: str) -> bool:
    """
    Dispatch a plain-text email with an arbitrary subject and body.
    Used by Graph 4 to send pre-built email payloads from A5.
    """
    return await _post("/send-email", {
        "to":        to,
        "subject":   subject,
        "body_text": body,
    })


async def send_interview_confirmation(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    interview_slot: str,
    zoom_url: str,
    interviewer_name: str = "the hiring team",
) -> bool:
    """Graph 3: final interview confirmation once candidate confirms their slot."""
    return await _post("/send-email", {
        "to": candidate_email,
        "subject": f"Interview Confirmed — {role_title}",
        "body_text": (
            f"Hi {candidate_name},\n\n"
            f"Your interview for the {role_title} role has been confirmed.\n\n"
            f"  Date/Time  : {interview_slot}\n"
            + (f"  Video Link : {zoom_url}\n" if zoom_url else "")
            + f"  Interviewer: {interviewer_name}\n\n"
            f"Please be ready 5 minutes before the scheduled time.\n\n"
            f"Best regards,\nThe Hiring Team"
        ),
    })
