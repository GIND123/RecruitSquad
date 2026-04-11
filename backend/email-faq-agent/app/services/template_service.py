from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from premailer import transform
from pathlib import Path
from typing import Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

TEMPLATE_REGISTRY: dict[str, dict] = {
    "welcome": {
        "file": "welcome.html",
        "required_fields": ["name", "email"],
        "description": "Welcome email for new users",
    },
    "password_reset": {
        "file": "password_reset.html",
        "required_fields": ["name", "reset_link"],
        "description": "Password reset instructions",
    },
    "reminder": {
        "file": "reminder.html",
        "required_fields": ["name", "reminder_text", "due_date"],
        "description": "Generic reminder email",
    },
    "notification": {
        "file": "notification.html",
        "required_fields": ["name", "message"],
        "description": "General notification email",
    },
    "interview_invite": {
        "file": "interview_invite.html",
        "required_fields": ["candidate_name", "interviewers"],
        "description": "Interview invitation email with Calendly booking links",
    },
}

EMAIL_TYPE_TO_TEMPLATE: dict[str, str] = {
    "welcome": "welcome",
    "onboarding": "welcome",
    "password_reset": "password_reset",
    "forgot_password": "password_reset",
    "reminder": "reminder",
    "task_reminder": "reminder",
    "notification": "notification",
    "alert": "notification",
}

_env: Optional[Environment] = None


def _get_env() -> Environment:
    global _env
    if _env is None:
        _env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    return _env


def resolve_template(email_type: str, template_name: Optional[str]) -> Optional[str]:
    if template_name and template_name in TEMPLATE_REGISTRY:
        return template_name
    mapped = EMAIL_TYPE_TO_TEMPLATE.get(email_type)
    if mapped:
        return mapped
    return None


def get_required_fields(template_name: str) -> list[str]:
    meta = TEMPLATE_REGISTRY.get(template_name)
    if not meta:
        return []
    return meta["required_fields"]


def validate_template_data(template_name: str, data: dict) -> list[str]:
    missing = []
    for field in get_required_fields(template_name):
        if field not in data:
            missing.append(field)
    return missing


def render_template(template_name: str, data: dict) -> str:
    meta = TEMPLATE_REGISTRY.get(template_name)
    if not meta:
        raise ValueError(f"Unknown template: {template_name}")
    env = _get_env()
    try:
        template = env.get_template(meta["file"])
        html = template.render(**data)
        inlined = transform(html)
        logger.info(f"Rendered template: {template_name}")
        return inlined
    except TemplateNotFound:
        raise ValueError(f"Template file not found: {meta['file']}")


def render_text_fallback(template_name: str, data: dict) -> str:
    lines = [f"Template: {template_name}"]
    for k, v in data.items():
        lines.append(f"{k}: {v}")
    return "\n".join(lines)


def list_templates() -> list[dict]:
    return [
        {
            "name": name,
            "required_fields": meta["required_fields"],
            "description": meta["description"],
        }
        for name, meta in TEMPLATE_REGISTRY.items()
    ]
