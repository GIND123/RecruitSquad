"""Tests for Stack Exchange helper service."""
from __future__ import annotations

import pytest

from app.utils.stackexchange import (
    evaluate_user_effectiveness,
    get_effectiveness_by_username,
    search_users_by_name,
)


def test_evaluate_user_effectiveness():
    user = {
        "user_id": 22656,
        "display_name": "Jon Skeet",
        "reputation": 1400000,
        "badge_counts": {"gold": 1500, "silver": 13000, "bronze": 18000},
        "link": "https://stackoverflow.com/users/22656/jon-skeet",
    }

    output = evaluate_user_effectiveness(user)
    assert output["user_id"] == 22656
    assert output["effectiveness_score"] <= 100


def test_search_users_by_name_no_api(monkeypatch):
    monkeypatch.setattr("app.utils.stackexchange.httpx.get", lambda *args, **kwargs: type("R", (), {
        "raise_for_status": lambda self: None,
        "json": lambda self: {"items": [{"user_id": 22656, "display_name": "Jon Skeet", "reputation": 1400000}]}
    })())

    users = search_users_by_name("Jon")
    assert users and users[0]["display_name"] == "Jon Skeet"


@pytest.mark.skip(reason="requires real StackExchange key / network")
def test_get_effectiveness_by_username_real():
    results = get_effectiveness_by_username("Jon")
    assert results
    assert results[0]["effectiveness_score"] >= 0
