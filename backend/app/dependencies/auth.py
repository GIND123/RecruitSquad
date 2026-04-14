"""
FastAPI auth dependencies — Firebase ID token verification.

Usage:
    @router.get("/protected")
    async def protected(user = Depends(get_current_user)):
        return {"uid": user["uid"]}

    @router.post("/manager-only")
    async def manager_only(user = Depends(require_manager)):
        ...
"""
from __future__ import annotations

import logging

import firebase_admin.auth
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """
    Verify the Firebase ID token in the Authorization: Bearer header.
    Returns the decoded token dict (contains uid, email, etc.).
    Raises 401 if the token is missing, invalid, or expired.
    """
    token = credentials.credentials
    try:
        decoded = firebase_admin.auth.verify_id_token(token)
        return decoded
    except firebase_admin.auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Token has expired. Please sign in again.")
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid authentication token.")
    except Exception as exc:
        logger.warning("[auth] Token verification failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authentication required.")


async def require_manager(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Extends get_current_user — additionally checks that the authenticated
    user has role='manager' in the Firestore 'users' collection.
    Raises 403 if the user is not a manager.
    """
    from app.services.firestore_service import get_db

    uid = current_user.get("uid", "")
    try:
        doc = get_db().collection("users").document(uid).get()
        if doc.exists and doc.to_dict().get("role") == "manager":
            return current_user
    except Exception as exc:
        logger.warning("[auth] Firestore role check failed uid=%s: %s", uid, exc)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail="Manager access required.")
