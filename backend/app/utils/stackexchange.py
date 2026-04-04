"""Stack Exchange helpers for candidate scorecard enrichment."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

STACKEXCHANGE_API_KEY = os.environ.get("STACKEXCHANGE_API_KEY", "")
STACKEXCHANGE_URL = "https://api.stackexchange.com/2.3"


def _default_params() -> dict[str, Any]:
    params = {"site": "stackoverflow", "pagesize": 20}
    if STACKEXCHANGE_API_KEY:
        params["key"] = STACKEXCHANGE_API_KEY
    return params


def search_users_by_tag(tag: str) -> list[dict[str, Any]]:
    """Search top users by a StackOverflow tag.

    Returns a list of users with reputation, profile links and badges.
    """
    url = f"{STACKEXCHANGE_URL}/tags/{tag}/top-answerers/all_time"
    params = _default_params()

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        return [
            {
                "user_id": i.get("user", {}).get("user_id"),
                "display_name": i.get("user", {}).get("display_name"),
                "reputation": i.get("user", {}).get("reputation"),
                "profile_url": i.get("user", {}).get("link"),
                "score": i.get("score"),
            }
            for i in items
        ]
    except Exception as exc:
        logger.warning("StackExchange request failed: %s", exc)
        return []


def search_users_by_name(username: str, pagesize: int = 10) -> list[dict[str, Any]]:
    """Search users by partial display name (inname query)."""
    url = f"{STACKEXCHANGE_URL}/users"
    params = {
        **_default_params(),
        "inname": username,
        "pagesize": pagesize,
        "order": "desc",
        "sort": "reputation",
    }

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except Exception as exc:
        logger.warning("StackExchange user search failed: %s", exc)
        return []


def get_user_details(user_id: int) -> dict[str, Any] | None:
    url = f"{STACKEXCHANGE_URL}/users/{user_id}"
    params = {
        **_default_params(),
        "filter": "!-*jbN0CeyJHb"  # minimal fields + badge_counts
    }

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        items = response.json().get("items", [])
        return items[0] if items else None
    except Exception as exc:
        logger.warning("StackExchange user fetch failed: %s", exc)
        return None


def evaluate_user_effectiveness(user: dict[str, Any]) -> dict[str, Any]:
    """Score Stack Exchange user effectiveness using reputation + badges."""
    reputation = user.get("reputation", 0)
    badge_counts = user.get("badge_counts", {})

    gold = badge_counts.get("gold", 0)
    silver = badge_counts.get("silver", 0)
    bronze = badge_counts.get("bronze", 0)

    effectiveness = min(100.0, reputation / 10000.0 + gold * 5 + silver * 1.5 + bronze * 0.5)
    return {
        "user_id": user.get("user_id"),
        "display_name": user.get("display_name"),
        "reputation": reputation,
        "badges": badge_counts,
        "effectiveness_score": round(effectiveness, 2),
        "profile_url": user.get("link"),
    }


def get_effectiveness_by_username(username: str, pagesize: int = 5) -> list[dict[str, Any]]:
    users = search_users_by_name(username, pagesize=pagesize)
    result = []
    for u in users:
        detail = get_user_details(u.get("user_id"))
        if detail:
            result.append(evaluate_user_effectiveness(detail))
    return result
