"""
A3 — Interview Coordinator
===========================
Creates interview scheduling links (self-hosted or Calendly) and Google Meet
links via the Google Calendar API when a candidate confirms their slot.

Required env vars (all optional — falls back gracefully):
  CALENDLY_API_KEY          Personal Access Token from Calendly app settings
  CALENDLY_EVENT_TYPE_UUID  UUID portion of the Calendly event type URL
  APP_URL                   Base URL used for self-hosted scheduling fallback

  Google Calendar (Service Account):
  GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT  Raw JSON of the service account key, OR
  GOOGLE_SERVICE_ACCOUNT_JSON          Path to the service account key JSON file
  FIREBASE_CLIENT_EMAIL + FIREBASE_PRIVATE_KEY  Reuse Firebase SA creds (fallback)
  GOOGLE_CALENDAR_ID            Calendar ID to create events on (default: primary)
"""
from __future__ import annotations

import json
import logging
import os
import uuid as _uuid_mod
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

_CALENDLY_BASE = "https://api.calendly.com"
_TIMEOUT       = 10.0


# ── Calendly ──────────────────────────────────────────────────────────────────

async def create_calendly_link(
    candidate_name: str,
    candidate_id: str,
    role_title: str,
) -> str:
    """
    Create a single-use Calendly scheduling link for one candidate.
    Returns the booking URL, or a placeholder if Calendly is not configured.
    """
    api_key    = os.environ.get("CALENDLY_API_KEY", "").strip()
    event_uuid = os.environ.get("CALENDLY_EVENT_TYPE_UUID", "").strip()

    if not api_key or not event_uuid:
        logger.info(
            "[A3] Calendly not configured — using placeholder link for candidate=%s",
            candidate_id,
        )
        return _placeholder_calendly(candidate_id)

    owner_uri = f"{_CALENDLY_BASE}/event_types/{event_uuid}"

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_CALENDLY_BASE}/scheduling_links",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "max_event_count": 1,
                    "owner":           owner_uri,
                    "owner_type":      "EventType",
                },
            )
            if resp.status_code in (200, 201):
                booking_url = resp.json().get("resource", {}).get("booking_url", "")
                if booking_url:
                    logger.info("[A3] Calendly link created candidate=%s url=%s",
                                candidate_id, booking_url)
                    return booking_url
            logger.warning("[A3] Calendly API %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("[A3] Calendly API call failed: %s", exc)

    return _placeholder_calendly(candidate_id)


def _placeholder_calendly(candidate_id: str) -> str:
    base = os.environ.get("APP_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/schedule/{candidate_id}"


# ── Google Calendar ───────────────────────────────────────────────────────────

def _get_google_credentials():
    """
    Load Google Service Account credentials from env.
    Returns a google.oauth2.service_account.Credentials object, or None.

    Resolution order:
      1. GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT  — raw JSON string
      2. GOOGLE_SERVICE_ACCOUNT_JSON          — path to a JSON key file
      3. FIREBASE_CLIENT_EMAIL + FIREBASE_PRIVATE_KEY  — reuse Firebase SA creds
    """
    try:
        from google.oauth2 import service_account  # type: ignore
    except ImportError:
        logger.warning("[A3] google-auth not installed — Google Calendar disabled")
        return None

    scopes = ["https://www.googleapis.com/auth/calendar"]

    # Option 1: raw JSON content in env var
    json_content = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT") or "").strip()
    if json_content:
        try:
            info = json.loads(json_content)
            return service_account.Credentials.from_service_account_info(info, scopes=scopes)
        except Exception as exc:
            logger.warning("[A3] Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT: %s", exc)

    # Option 2: path to JSON file
    json_path = (os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    if json_path and os.path.isfile(json_path):
        try:
            return service_account.Credentials.from_service_account_file(json_path, scopes=scopes)
        except Exception as exc:
            logger.warning("[A3] Failed to load service account from %s: %s", json_path, exc)

    # Option 3: reuse Firebase service account env vars (already in .env)
    client_email = (os.environ.get("FIREBASE_CLIENT_EMAIL") or "").strip()
    private_key  = (os.environ.get("FIREBASE_PRIVATE_KEY") or "").strip()
    project_id   = (os.environ.get("FIREBASE_PROJECT_ID") or "").strip()
    if client_email and private_key:
        try:
            info = {
                "type":                        "service_account",
                "project_id":                  project_id,
                "private_key":                 private_key.replace("\\n", "\n"),
                "client_email":                client_email,
                "token_uri":                   "https://oauth2.googleapis.com/token",
            }
            logger.info("[A3] Using Firebase service account for Google Calendar: %s", client_email)
            return service_account.Credentials.from_service_account_info(info, scopes=scopes)
        except Exception as exc:
            logger.warning("[A3] Failed to build credentials from Firebase SA env vars: %s", exc)

    return None


async def create_google_calendar_event(
    candidate_name: str,
    candidate_email: str,
    role_title: str,
    slot_iso: str,
    slot_timezone: str = "UTC",
    duration_minutes: int = 60,
) -> str:
    """
    Create a Google Calendar event with a Google Meet link for the interview.

    Returns the Google Meet join URL, or a placeholder string if Google Calendar
    is not configured or the API call fails.
    """
    import asyncio

    creds = _get_google_credentials()
    if not creds:
        logger.info("[A3] Google Calendar not configured — skipping event creation")
        return ""

    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "primary").strip() or "primary"

    def _create_event_sync() -> str:
        try:
            from googleapiclient.discovery import build  # type: ignore
        except ImportError:
            logger.warning("[A3] google-api-python-client not installed")
            return ""

        try:
            service = build("calendar", "v3", credentials=creds, cache_discovery=False)

            # Parse the ISO slot and compute end time
            start_dt = datetime.fromisoformat(slot_iso.replace("Z", "+00:00"))
            end_dt   = start_dt + timedelta(minutes=duration_minutes)

            event_body = {
                "summary": f"Interview: {role_title} — {candidate_name}",
                "description": (
                    f"Interview for the {role_title} position.\n"
                    f"Candidate: {candidate_name} ({candidate_email})"
                ),
                "start": {
                    "dateTime": start_dt.isoformat(),
                    "timeZone": slot_timezone,
                },
                "end": {
                    "dateTime": end_dt.isoformat(),
                    "timeZone": slot_timezone,
                },
                "attendees": [
                    {"email": candidate_email, "displayName": candidate_name},
                ],
                "conferenceData": {
                    "createRequest": {
                        "requestId": str(_uuid_mod.uuid4()),
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "email",  "minutes": 60},
                        {"method": "popup",  "minutes": 10},
                    ],
                },
            }

            created = (
                service.events()
                .insert(
                    calendarId=calendar_id,
                    body=event_body,
                    conferenceDataVersion=1,
                    sendUpdates="all",  # sends invite email to attendees
                )
                .execute()
            )

            # Extract the Meet link
            meet_link = (
                created.get("conferenceData", {})
                       .get("entryPoints", [{}])[0]
                       .get("uri", "")
            )
            logger.info(
                "[A3] Google Calendar event created: %s meet=%s",
                created.get("htmlLink", ""),
                meet_link,
            )
            return meet_link

        except Exception as exc:
            logger.warning("[A3] Google Calendar API call failed: %s", exc)
            return ""

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create_event_sync)
