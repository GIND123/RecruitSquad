from typing import Any
import google.generativeai.protos as protos
from app.services.user_store import get_all_users, get_user_by_id, get_user_by_email
from app.services.template_service import (
    list_templates,
    render_template,
    render_text_fallback,
    validate_template_data,
)
from app.services.email_service import send_email
from app.kafka.producer import publish_email_job
from app.models.email_models import Priority
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Tool schema for Gemini ─────────────────────────────────────────────────────
# Gemini uses protos.Tool / FunctionDeclaration instead of raw dicts.

def _s(type_: protos.Type, description: str = "", **kwargs) -> protos.Schema:
    return protos.Schema(type=type_, description=description, **kwargs)


GEMINI_TOOLS = protos.Tool(
    function_declarations=[
        protos.FunctionDeclaration(
            name="list_users",
            description=(
                "Return all users in the system. Use this first when the task mentions "
                "a person by name or role so you can resolve their email address."
            ),
            parameters=protos.Schema(type=protos.Type.OBJECT, properties={}),
        ),
        protos.FunctionDeclaration(
            name="get_user",
            description="Look up a single user by their ID (e.g. u001) or email address.",
            parameters=protos.Schema(
                type=protos.Type.OBJECT,
                properties={
                    "user_id": _s(protos.Type.STRING, "User ID like u001"),
                    "email": _s(protos.Type.STRING, "User email address"),
                },
            ),
        ),
        protos.FunctionDeclaration(
            name="list_templates",
            description=(
                "Return all available email templates with their names, descriptions, "
                "and required variables. Always call this before send_email with a template."
            ),
            parameters=protos.Schema(type=protos.Type.OBJECT, properties={}),
        ),
        protos.FunctionDeclaration(
            name="send_email",
            description=(
                "Send an email immediately via SMTP. "
                "Provide template_name + template_data, or write body_html / body_text directly."
            ),
            parameters=protos.Schema(
                type=protos.Type.OBJECT,
                required=["to", "subject"],
                properties={
                    "to": _s(protos.Type.STRING, "Recipient email address"),
                    "subject": _s(protos.Type.STRING, "Email subject line"),
                    "template_name": _s(protos.Type.STRING, "Registered template name"),
                    "template_data": _s(protos.Type.STRING, "JSON-encoded template variables"),
                    "body_html": _s(protos.Type.STRING, "Raw HTML body — use when no template fits"),
                    "body_text": _s(protos.Type.STRING, "Plain-text fallback body"),
                },
            ),
        ),
        protos.FunctionDeclaration(
            name="enqueue_email",
            description=(
                "Queue an email job to Kafka for async processing. "
                "Use for bulk sends, low-priority emails, or explicit async requests."
            ),
            parameters=protos.Schema(
                type=protos.Type.OBJECT,
                required=["to", "subject"],
                properties={
                    "to": _s(protos.Type.STRING, "Recipient email address"),
                    "subject": _s(protos.Type.STRING, "Email subject line"),
                    "template_name": _s(protos.Type.STRING, "Registered template name"),
                    "template_data": _s(protos.Type.STRING, "JSON-encoded template variables"),
                    "body_text": _s(protos.Type.STRING, "Plain-text body"),
                    "priority": _s(protos.Type.STRING, "high | normal | low"),
                },
            ),
        ),
    ]
)

# ── Tool executor (model-agnostic) ─────────────────────────────────────────────

async def execute_tool(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    import json

    logger.info(f"Executing tool: {name} | inputs={inputs}")

    # Gemini passes object fields as JSON strings when schema type is STRING
    # so we decode template_data here if needed
    def _decode(val: Any) -> dict:
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return {}
        return val or {}

    if name == "list_users":
        return {"users": get_all_users()}

    if name == "get_user":
        user = None
        if user_id := inputs.get("user_id"):
            user = get_user_by_id(user_id)
        elif email := inputs.get("email"):
            user = get_user_by_email(email)
        return {"user": user} if user else {"error": "User not found"}

    if name == "list_templates":
        return {"templates": list_templates()}

    if name == "send_email":
        body_html = inputs.get("body_html")
        body_text = inputs.get("body_text")
        template_name = inputs.get("template_name")
        template_data = _decode(inputs.get("template_data"))

        if template_name:
            missing = validate_template_data(template_name, template_data)
            if missing:
                return {"error": f"Missing template fields: {', '.join(missing)}"}
            body_html = render_template(template_name, template_data)
            if not body_text:
                body_text = render_text_fallback(template_name, template_data)

        try:
            await send_email(
                to=inputs["to"],
                subject=inputs["subject"],
                body_text=body_text,
                body_html=body_html,
            )
            return {"status": "sent", "to": inputs["to"], "subject": inputs["subject"]}
        except Exception as exc:
            return {"error": str(exc)}

    if name == "enqueue_email":
        try:
            priority = Priority(inputs.get("priority", "normal"))
            template_data = _decode(inputs.get("template_data"))
            job_id = await publish_email_job(
                to=inputs["to"],
                subject=inputs["subject"],
                body_text=inputs.get("body_text"),
                template_name=inputs.get("template_name"),
                template_data=template_data if template_data else None,
                priority=priority,
            )
            return {"status": "queued", "job_id": job_id, "to": inputs["to"]}
        except Exception as exc:
            return {"error": str(exc)}

    return {"error": f"Unknown tool: {name}"}