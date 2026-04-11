import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_get_templates():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/templates")
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["templates"]]
    assert "welcome" in names


@pytest.mark.asyncio
async def test_send_email_with_template():
    with patch("app.main.send_email", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/send-email", json={
                "to": "user@example.com",
                "subject": "Welcome",
                "template_name": "welcome",
                "template_data": {"name": "Alice", "email": "user@example.com"},
            })
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_send_email_missing_template_data():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/send-email", json={
            "to": "user@example.com",
            "subject": "Welcome",
            "template_name": "welcome",
        })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_enqueue_email():
    with patch("app.main.publish_email_job", new_callable=AsyncMock, return_value="test-job-id"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/enqueue-email", json={
                "to": "user@example.com",
                "subject": "Hello",
                "body_text": "Plain text",
            })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["job_id"] == "test-job-id"


@pytest.mark.asyncio
async def test_agent_email_task_immediate():
    with patch("app.agent.orchestrator.send_email", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/agent/email-task", json={
                "email_type": "welcome",
                "recipient": "new@example.com",
                "template_data": {"name": "New User", "email": "new@example.com"},
                "send_mode": "immediate",
            })
    assert resp.status_code == 200
    assert resp.json()["action_taken"] == "sent_immediately"


@pytest.mark.asyncio
async def test_agent_email_task_validation_error():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agent/email-task", json={
            "email_type": "welcome",
            "recipient": "bad@example.com",
            "template_data": {},
            "send_mode": "immediate",
        })
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
