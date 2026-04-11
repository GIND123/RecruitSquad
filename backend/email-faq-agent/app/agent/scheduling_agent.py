"""
Interview Scheduling Agent
==========================
Two entry points:

send_interview_invite(ScheduleRequest)
    Core function: given structured candidate + interviewer info, renders
    the interview_invite.html template and sends the email via SMTP.
    Used directly by the agentic loop below as a tool.

run_scheduling_agent(task: str)
    Agentic entry point: accepts a plain-English instruction, uses Gemini
    with two tools (list_users, send_interview_invite) to resolve names,
    look up Calendly links, and fire the invite — all autonomously.

Example tasks
-------------
  "Schedule an interview for John Doe (john@example.com) with User1 and User2"
  "Send an interview invite to alice@company.com, interviewer should be David Lee"
  "Book an interview for candidate jane@test.com with all admin users"
"""

import json
import google.generativeai as genai
import google.generativeai.protos as protos

from app.models.scheduling_models import (
    AIScheduleResponse,
    InterviewerInfo,
    ScheduleRequest,
    ScheduleResponse,
)
from app.services.user_store import get_all_users, get_user_by_id
from app.services.email_service import send_email
from app.services.template_service import render_template
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_TEMPLATE = "interview_invite"


# ── Core invite sender (also called as a Gemini tool) ─────────────────────────

def _render_plain_text(
    candidate_name: str,
    interviewers: list[InterviewerInfo],
    custom_message: str,
) -> str:
    lines = [f"Hi {candidate_name},", ""]
    lines.append(
        "We'd like to invite you for an interview. "
        "Please book a slot using one of the links below:"
    )
    lines.append("")
    if custom_message:
        lines += [custom_message, ""]
    for iv in interviewers:
        lines.append(f"  • {iv.name}: {iv.calendly_link}")
    lines += [
        "",
        "Once booked, you'll receive a calendar invitation with all meeting details.",
        "",
        "Looking forward to speaking with you.",
    ]
    return "\n".join(lines)


async def send_interview_invite(request: ScheduleRequest) -> ScheduleResponse:
    """Load interviewers, render the invite email, and send it to the candidate."""
    interviewers: list[InterviewerInfo] = []
    not_found: list[str] = []
    missing_link: list[str] = []

    for uid in request.interviewer_user_ids:
        user = get_user_by_id(uid)
        if not user:
            not_found.append(uid)
            continue
        link = (user.get("calendly_link") or "").strip()
        if not link:
            missing_link.append(user["name"])
            continue
        interviewers.append(InterviewerInfo(name=user["name"], calendly_link=link))

    if not_found:
        return ScheduleResponse(
            status="error",
            message=f"Interviewer user ID(s) not found: {', '.join(not_found)}",
            candidate_email=str(request.candidate_email),
            interviewers=[],
            links_sent=[],
        )
    if missing_link:
        return ScheduleResponse(
            status="error",
            message=f"No calendly_link configured for: {', '.join(missing_link)}",
            candidate_email=str(request.candidate_email),
            interviewers=interviewers,
            links_sent=[],
        )

    template_data = {
        "candidate_name": request.candidate_name,
        "interviewers": [iv.model_dump() for iv in interviewers],
        "custom_message": request.custom_message or "",
    }
    try:
        body_html = render_template(_TEMPLATE, template_data)
    except Exception as exc:
        logger.warning(f"Template render failed: {exc} — using plain text")
        body_html = None

    body_text = _render_plain_text(
        request.candidate_name, interviewers, request.custom_message or ""
    )

    logger.info(
        f"Sending interview invite | candidate={request.candidate_email} "
        f"interviewers={[iv.name for iv in interviewers]}"
    )
    try:
        await send_email(
            to=str(request.candidate_email),
            subject=request.subject,
            body_text=body_text,
            body_html=body_html,
        )
    except Exception as exc:
        logger.error(f"Failed to send invite to {request.candidate_email}: {exc}")
        return ScheduleResponse(
            status="error",
            message=f"Email delivery failed: {exc}",
            candidate_email=str(request.candidate_email),
            interviewers=interviewers,
            links_sent=[],
        )

    names = [iv.name for iv in interviewers]
    return ScheduleResponse(
        status="sent",
        message=(
            f"Interview invitation sent to {request.candidate_name} "
            f"({request.candidate_email}) with links for: {', '.join(names)}."
        ),
        candidate_email=str(request.candidate_email),
        interviewers=interviewers,
        links_sent=[iv.calendly_link for iv in interviewers],
    )


# ── Gemini tool definitions ────────────────────────────────────────────────────

def _s(type_: protos.Type, description: str = "") -> protos.Schema:
    return protos.Schema(type=type_, description=description)


_SCHEDULING_TOOLS = protos.Tool(
    function_declarations=[
        protos.FunctionDeclaration(
            name="list_users",
            description=(
                "Return all users in the system with their IDs, names, roles, and "
                "Calendly links. Always call this first to resolve interviewer names "
                "to user IDs before calling send_interview_invite."
            ),
            parameters=protos.Schema(type=protos.Type.OBJECT, properties={}),
        ),
        protos.FunctionDeclaration(
            name="send_interview_invite",
            description=(
                "Send an interview invitation email to the candidate. The email includes "
                "a Calendly booking link for each interviewer so the candidate can "
                "self-select a convenient time slot."
            ),
            parameters=protos.Schema(
                type=protos.Type.OBJECT,
                required=["candidate_name", "candidate_email", "interviewer_user_ids"],
                properties={
                    "candidate_name": _s(protos.Type.STRING, "Candidate's full name"),
                    "candidate_email": _s(protos.Type.STRING, "Candidate's email address"),
                    "interviewer_user_ids": _s(
                        protos.Type.STRING,
                        'JSON array of user IDs resolved from list_users, e.g. ["u001","u002"]',
                    ),
                    "subject": _s(protos.Type.STRING, "Email subject line (optional)"),
                    "custom_message": _s(
                        protos.Type.STRING,
                        "Extra note to include in the email body (optional)",
                    ),
                },
            ),
        ),
    ]
)

_SYSTEM_PROMPT = """\
You are an interview scheduling agent. You receive plain-English scheduling requests
and execute them by calling tools.

Rules:
- Always call list_users first to find available users and their IDs.
- Match interviewer names or roles from the task to actual users in the system.
- The candidate's email address must appear explicitly in the task — never invent one.
  If it is missing, reply explaining that the candidate email is required.
- Once you have the candidate info and resolved interviewer IDs, call send_interview_invite.
- After completing the task, give a concise plain-English summary of what you did.
- If anything fails (user not found, missing email, send error), explain clearly why.
"""


# ── Gemini response helpers (mirrors ai_agent.py) ─────────────────────────────

def _extract_text(response: genai.types.GenerateContentResponse) -> str:
    for part in response.parts:
        if hasattr(part, "text") and part.text:
            return part.text
    return "Task completed."


def _extract_function_calls(response: genai.types.GenerateContentResponse) -> list:
    calls = []
    for part in response.parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            calls.append(fc)
    return calls


# ── Tool executor ──────────────────────────────────────────────────────────────

async def _execute_tool(name: str, inputs: dict) -> dict:
    if name == "list_users":
        return {"users": get_all_users()}

    if name == "send_interview_invite":
        # Gemini passes arrays as JSON strings when schema type is STRING
        raw_ids = inputs.get("interviewer_user_ids", "[]")
        if isinstance(raw_ids, str):
            try:
                interviewer_ids = json.loads(raw_ids)
            except Exception:
                interviewer_ids = [raw_ids]
        else:
            interviewer_ids = list(raw_ids)

        req = ScheduleRequest(
            candidate_name=inputs["candidate_name"],
            candidate_email=inputs["candidate_email"],
            interviewer_user_ids=interviewer_ids,
            subject=inputs.get("subject", "Interview Invitation"),
            custom_message=inputs.get("custom_message") or None,
        )
        resp = await send_interview_invite(req)
        return resp.model_dump()

    return {"error": f"Unknown tool: {name}"}


# ── Agentic entry point ────────────────────────────────────────────────────────

async def run_scheduling_agent(task: str) -> AIScheduleResponse:
    """
    Accept a plain-English scheduling task, run a Gemini tool-calling loop,
    and return a structured result once the agent is done.
    """
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=_SYSTEM_PROMPT,
        tools=[_SCHEDULING_TOOLS],
        generation_config=genai.types.GenerationConfig(temperature=0),
    )
    chat = model.start_chat()

    logger.info(f"Scheduling agent starting | task={task!r}")
    response = await chat.send_message_async(task)

    invite_result: dict = {}

    while True:
        fn_calls = _extract_function_calls(response)

        if not fn_calls:
            # Agent is done — extract its final summary
            summary = _extract_text(response)
            status = "sent" if invite_result.get("status") == "sent" else "failed"
            logger.info(f"Scheduling agent done | status={status}")
            return AIScheduleResponse(
                status=status,
                summary=summary,
                candidate_email=invite_result.get("candidate_email", ""),
                interviewers=[
                    InterviewerInfo(**iv)
                    for iv in invite_result.get("interviewers", [])
                ],
                links_sent=invite_result.get("links_sent", []),
            )

        # Execute each tool call and feed results back
        response_parts = []
        for fc in fn_calls:
            raw_inputs = dict(fc.args)
            result = await _execute_tool(fc.name, raw_inputs)
            logger.info(f"Tool called: {fc.name} | status={result.get('status', 'ok')}")

            if fc.name == "send_interview_invite":
                invite_result = result  # capture for final response

            response_parts.append(
                protos.Part(
                    function_response=protos.FunctionResponse(
                        name=fc.name,
                        response={"result": json.dumps(result, default=str)},
                    )
                )
            )

        response = await chat.send_message_async(response_parts)
