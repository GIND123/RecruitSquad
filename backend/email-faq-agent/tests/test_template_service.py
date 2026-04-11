import pytest
from app.services.template_service import (
    resolve_template,
    validate_template_data,
    render_template,
    render_text_fallback,
    list_templates,
)


def test_resolve_template_direct():
    assert resolve_template("welcome", "welcome") == "welcome"


def test_resolve_template_from_email_type():
    assert resolve_template("forgot_password", None) == "password_reset"
    assert resolve_template("onboarding", None) == "welcome"
    assert resolve_template("alert", None) == "notification"


def test_resolve_template_unknown():
    assert resolve_template("nonexistent", None) is None


def test_validate_template_data_ok():
    missing = validate_template_data("welcome", {"name": "Alice", "email": "a@b.com"})
    assert missing == []


def test_validate_template_data_missing():
    missing = validate_template_data("welcome", {"name": "Alice"})
    assert "email" in missing


def test_render_template_welcome():
    html = render_template("welcome", {"name": "Alice", "email": "a@b.com"})
    assert "Alice" in html
    assert "a@b.com" in html


def test_render_template_password_reset():
    html = render_template("password_reset", {"name": "Bob", "reset_link": "https://example.com/reset"})
    assert "Bob" in html
    assert "https://example.com/reset" in html


def test_render_template_reminder():
    html = render_template("reminder", {"name": "Carol", "reminder_text": "Submit report", "due_date": "2024-12-01"})
    assert "Submit report" in html
    assert "2024-12-01" in html


def test_render_template_notification():
    html = render_template("notification", {"name": "Dan", "message": "Server is down"})
    assert "Server is down" in html


def test_render_template_unknown():
    with pytest.raises(ValueError):
        render_template("nonexistent", {})


def test_render_text_fallback():
    text = render_text_fallback("welcome", {"name": "Alice", "email": "a@b.com"})
    assert "name: Alice" in text
    assert "email: a@b.com" in text


def test_list_templates():
    templates = list_templates()
    names = [t["name"] for t in templates]
    assert "welcome" in names
    assert "password_reset" in names
    assert "reminder" in names
    assert "notification" in names
