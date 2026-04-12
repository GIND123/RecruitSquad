"""
Tests for the interview scheduling agent (email-link approach).
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.scheduling_models import ScheduleRequest
from app.agent.scheduling_agent import send_interview_invite


# ── send_interview_invite unit tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_invite_sent_successfully():
    with patch("app.agent.scheduling_agent.send_email", new_callable=AsyncMock):
        req = ScheduleRequest(
            candidate_name="John Doe",
            candidate_email="john@example.com",
            interviewer_user_ids=["u001", "u002"],
            subject="Interview Invitation",
        )
        resp = await send_interview_invite(req)

    assert resp.status == "sent"
    assert resp.candidate_email == "john@example.com"
    assert len(resp.interviewers) == 2
    assert len(resp.links_sent) == 2
    assert all("calendly.com" in link for link in resp.links_sent)
    assert "John Doe" in resp.message


@pytest.mark.asyncio
async def test_invite_with_custom_message():
    with patch("app.agent.scheduling_agent.send_email", new_callable=AsyncMock) as mock_send:
        req = ScheduleRequest(
            candidate_name="Jane Smith",
            candidate_email="jane@example.com",
            interviewer_user_ids=["u001"],
            custom_message="We loved your portfolio!",
        )
        resp = await send_interview_invite(req)

    assert resp.status == "sent"
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_invite_user_not_found():
    req = ScheduleRequest(
        candidate_name="Alice",
        candidate_email="alice@example.com",
        interviewer_user_ids=["u999"],
    )
    resp = await send_interview_invite(req)

    assert resp.status == "error"
    assert "u999" in resp.message
    assert resp.links_sent == []


@pytest.mark.asyncio
async def test_invite_missing_calendly_link():
    fake_user = {"id": "u_fake", "name": "No Link User", "email": "nolink@example.com", "calendly_link": ""}

    with patch("app.agent.scheduling_agent.get_user_by_id", return_value=fake_user):
        req = ScheduleRequest(
            candidate_name="Bob",
            candidate_email="bob@example.com",
            interviewer_user_ids=["u_fake"],
        )
        resp = await send_interview_invite(req)

    assert resp.status == "error"
    assert "No Link User" in resp.message
    assert resp.links_sent == []


@pytest.mark.asyncio
async def test_invite_email_delivery_failure():
    with patch(
        "app.agent.scheduling_agent.send_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP connection refused"),
    ):
        req = ScheduleRequest(
            candidate_name="Charlie",
            candidate_email="charlie@example.com",
            interviewer_user_ids=["u001"],
        )
        resp = await send_interview_invite(req)

    assert resp.status == "error"
    assert "SMTP" in resp.message or "failed" in resp.message.lower()
    assert resp.links_sent == []


@pytest.mark.asyncio
async def test_invite_multiple_interviewers_all_links_included():
    with patch("app.agent.scheduling_agent.send_email", new_callable=AsyncMock):
        req = ScheduleRequest(
            candidate_name="Diana",
            candidate_email="diana@example.com",
            interviewer_user_ids=["u001", "u002", "u003"],
        )
        resp = await send_interview_invite(req)

    # u003 (Carol Williams) has a placeholder calendly link — still valid format
    assert resp.status == "sent"
    assert len(resp.links_sent) == 3
    interviewer_names = [iv.name for iv in resp.interviewers]
    assert "Rupali Patel" in interviewer_names
    assert "Adwaith Santosh" in interviewer_names


# ── Endpoint integration tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_schedule_interview_endpoint_success():
    with patch("app.agent.scheduling_agent.send_email", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/agent/schedule-interview", json={
                "candidate_name": "Eve",
                "candidate_email": "eve@example.com",
                "interviewer_user_ids": ["u001"],
                "subject": "Tech Interview",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "sent"
    assert data["candidate_email"] == "eve@example.com"
    assert len(data["links_sent"]) == 1


@pytest.mark.asyncio
async def test_schedule_interview_endpoint_missing_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agent/schedule-interview", json={
            "candidate_name": "Frank",
            # missing candidate_email and interviewer_user_ids
        })

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_schedule_interview_endpoint_invalid_email():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agent/schedule-interview", json={
            "candidate_name": "Grace",
            "candidate_email": "not-an-email",
            "interviewer_user_ids": ["u001"],
        })

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_schedule_interview_endpoint_unknown_interviewer():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/agent/schedule-interview", json={
            "candidate_name": "Hank",
            "candidate_email": "hank@example.com",
            "interviewer_user_ids": ["u_does_not_exist"],
        })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "u_does_not_exist" in data["message"]
