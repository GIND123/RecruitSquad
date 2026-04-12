import json
from pathlib import Path
from typing import Optional

_USERS_FILE = Path(__file__).parent.parent.parent / "users.json"


def _load() -> list[dict]:
    with open(_USERS_FILE) as f:
        return json.load(f)["users"]


def get_all_users() -> list[dict]:
    return _load()


def get_user_by_id(user_id: str) -> Optional[dict]:
    return next((u for u in _load() if u["id"] == user_id), None)


def get_user_by_email(email: str) -> Optional[dict]:
    return next((u for u in _load() if u["email"].lower() == email.lower()), None)