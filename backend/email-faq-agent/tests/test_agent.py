import pytest
from unittest.mock import AsyncMock, patch
from app.models.email_models import AgentTaskRequest, SendMode, Priority


@pytest.mark.asyncio
async def test_agent_immediate_send():
    with patch("app.agent.orchestrator.send_email", new_callable=AsyncMock) as mock_send:
        from app.agent.orchestrator import handle_email_task
        req = AgentTaskRequest(
            email_type="welcome",
            recipient="alice@example.com",
            template_data={"name": "Alice", "email": "alice@example.com"},
            send_mode=SendMode.immediate,
        )
        resp = await handle_email_task(req)
        assert resp.status == "success"
        assert resp.action_taken == "sent_immediately"
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_agent_queued_send():
    with patch("app.agent.orchestrator.publish_email_job", new_callable=AsyncMock, return_value="job-123") as mock_pub:
        from app.agent.orchestrator import handle_email_task
        req = AgentTaskRequest(
            email_type="notification",
            recipient="bob@example.com",
            template_data={"name": "Bob", "message": "Hello"},
            send_mode=SendMode.queued,
        )
        resp = await handle_email_task(req)
        assert resp.status == "success"
        assert resp.action_taken == "enqueued"
        assert resp.job_id == "job-123"
        mock_pub.assert_called_once()


@pytest.mark.asyncio
async def test_agent_validation_failure():
    from app.agent.orchestrator import handle_email_task
    req = AgentTaskRequest(
        email_type="welcome",
        recipient="carol@example.com",
        template_data={"name": "Carol"},  # missing "email"
        send_mode=SendMode.immediate,
    )
    resp = await handle_email_task(req)
    assert resp.status == "rejected"
    assert resp.action_taken == "validation_failed"
    assert "email" in resp.message


@pytest.mark.asyncio
async def test_agent_auto_mode_high_priority_sends_immediately():
    with patch("app.agent.orchestrator.send_email", new_callable=AsyncMock) as mock_send:
        from app.agent.orchestrator import handle_email_task
        req = AgentTaskRequest(
            email_type="notification",
            recipient="dave@example.com",
            template_data={"name": "Dave", "message": "Urgent"},
            send_mode=SendMode.auto,
            priority=Priority.high,
        )
        resp = await handle_email_task(req)
        assert resp.action_taken == "sent_immediately"
        mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_agent_send_failure_returns_error():
    import aiosmtplib
    with patch("app.agent.orchestrator.send_email", new_callable=AsyncMock, side_effect=aiosmtplib.SMTPException("fail")):
        from app.agent.orchestrator import handle_email_task
        req = AgentTaskRequest(
            email_type="notification",
            recipient="err@example.com",
            template_data={"name": "Err", "message": "test"},
            send_mode=SendMode.immediate,
        )
        resp = await handle_email_task(req)
        assert resp.status == "error"
        assert resp.action_taken == "send_failed"
