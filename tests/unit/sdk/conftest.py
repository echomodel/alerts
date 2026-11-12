"""Fixtures for SDK tests: an isolated store, a caller, and a network-free channel.

The ``capture://`` Apprise scheme below is a custom plugin registered for the
test session; it records every notification instead of sending one, so the
real Apprise pipeline runs end to end with no network.
"""

from __future__ import annotations

import pytest
from apprise.decorators import notify as apprise_notify

import mcp_app
from mcp_app.context import current_user
from mcp_app.data_store import FileSystemUserDataStore
from mcp_app.models import UserRecord

SENT: list[dict] = []


@apprise_notify(on="capture")
def _capture(body, title, notify_type, *args, **kwargs):
    meta = kwargs.get("meta") or {}
    SENT.append({"title": title, "body": body, "type": str(notify_type), "host": meta.get("host")})
    return True


@apprise_notify(on="failing")
def _failing(body, title, notify_type, *args, **kwargs):
    return False


@pytest.fixture
def sent():
    SENT.clear()
    yield SENT
    SENT.clear()


@pytest.fixture
def store(tmp_path, monkeypatch):
    """mcp-app's filesystem store on a temp dir, as the running app would set it."""
    monkeypatch.setenv("APP_USERS_PATH", str(tmp_path / "users"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("ALERTS_CHANNELS", raising=False)
    monkeypatch.setattr(mcp_app, "_store", FileSystemUserDataStore(app_name="alerts"))
    monkeypatch.setattr(mcp_app, "_transport", "http")
    return mcp_app._store


@pytest.fixture
def as_user(store):
    """Set ``current_user`` for the test; returns a function to switch users."""
    tokens = []

    def _set(email: str):
        tokens.append(current_user.set(UserRecord(email=email)))
        return email

    yield _set
    for t in reversed(tokens):
        try:
            current_user.reset(t)
        except ValueError:
            # An async test's set() ran in the task's own context copy, which
            # is gone with the task; there is nothing left to reset.
            pass


@pytest.fixture
def channels_env(monkeypatch):
    """Define channels through the environment variable, the container route."""

    def _set(text: str):
        monkeypatch.setenv("ALERTS_CHANNELS", text)

    return _set


@pytest.fixture
def stdio(monkeypatch):
    monkeypatch.setattr(mcp_app, "_transport", "stdio")


@pytest.fixture
def admin(monkeypatch):
    """Make an email an administrator the way a deployment does."""

    def _set(email: str):
        monkeypatch.setenv("ADMIN_EMAILS", email)

    return _set
