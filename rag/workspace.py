"""Phạm vi tài khoản theo request; CLI local vẫn dùng thư viện gốc."""

from contextlib import contextmanager
from contextvars import ContextVar

from rag.config import get_settings

_current_user = ContextVar("workspace_user", default=None)


def current_user() -> dict | None:
    return _current_user.get()


@contextmanager
def user_scope(user: dict):
    token = _current_user.set(user)
    try:
        yield
    finally:
        _current_user.reset(token)


def workspace_roots():
    settings, user = get_settings(), current_user()
    if user is None or user["legacy_workspace"]:
        return settings.data_dir, settings.vector_db_dir
    return (settings.data_dir / ".users" / user["id"],
            settings.vector_db_dir / ".users" / user["id"])


def preview_scope(topic: str) -> str:
    user = current_user()
    return f"{user['id']}:{topic}" if user else topic
