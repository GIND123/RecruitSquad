from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.dependencies.auth import get_current_user
from app.models.schemas import OrgCreateRequest
from app.services.firestore_service import create_org, get_all_orgs, get_org, join_org

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orgs", tags=["orgs"])


@router.get("")
async def list_orgs():
    """Public — list all organisations."""
    return {"orgs": get_all_orgs()}


@router.get("/{org_id}")
async def get_org_detail(org_id: str):
    """Public — get a single organisation."""
    org = get_org(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organisation not found")
    return org


@router.post("", status_code=201)
async def create_organisation(
    payload: OrgCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Authenticated — create a new organisation and become its first manager.
    The calling user's Firestore profile is updated: role=manager, org_id, org_name.
    Sends a welcome email to the registering manager and a notification to the admin.
    """
    uid = current_user.get("uid", "")
    manager_email = current_user.get("email", "")
    manager_name = current_user.get("name", "") or manager_email.split("@")[0]

    org_id = create_org(
        name=payload.name,
        creator_uid=uid,
        creator_email=manager_email,
        creator_name=manager_name,
        website=payload.website,
        description=payload.description,
    )
    logger.info("[orgs] created org=%s name=%r by uid=%s", org_id, payload.name, uid)

    from app.services.a6_client import send_org_welcome, send_org_admin_notification

    if manager_email:
        background_tasks.add_task(
            send_org_welcome,
            manager_name=manager_name,
            manager_email=manager_email,
            org_name=payload.name,
            org_website=payload.website,
        )
    background_tasks.add_task(
        send_org_admin_notification,
        manager_name=manager_name,
        manager_email=manager_email,
        org_name=payload.name,
        org_website=payload.website,
        action="registered",
    )

    return {"org_id": org_id, "name": payload.name}


@router.post("/{org_id}/join", status_code=200)
async def join_organisation(
    org_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """
    Authenticated — join an existing organisation as a manager.
    Updates the user's Firestore profile: role=manager, org_id, org_name.
    Sends a welcome email to the joining manager and a notification to the admin.
    """
    uid = current_user.get("uid", "")
    manager_email = current_user.get("email", "")
    manager_name = current_user.get("name", "") or manager_email.split("@")[0]

    ok = join_org(uid=uid, org_id=org_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Organisation not found")

    org = get_org(org_id) or {}
    org_name = org.get("name", "")
    org_website = org.get("website", "")
    logger.info("[orgs] uid=%s joined org=%s name=%r", uid, org_id, org_name)

    from app.services.a6_client import send_org_welcome, send_org_admin_notification

    if manager_email:
        background_tasks.add_task(
            send_org_welcome,
            manager_name=manager_name,
            manager_email=manager_email,
            org_name=org_name,
            org_website=org_website,
        )
    background_tasks.add_task(
        send_org_admin_notification,
        manager_name=manager_name,
        manager_email=manager_email,
        org_name=org_name,
        org_website=org_website,
        action="joined",
    )

    return {"org_id": org_id, "name": org_name}
