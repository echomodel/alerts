"""Grants: per-user, isolated, and defaults that follow the rules."""

from alerts.sdk import grants


def test_grant_first_channel_becomes_default(store):
    g = grants.grant("a@example.com", "phone")
    assert g == {"channels": ["phone"], "default": "phone"}


def test_second_grant_keeps_default_unless_asked(store):
    grants.grant("a@example.com", "phone")
    g = grants.grant("a@example.com", "work")
    assert g["channels"] == ["phone", "work"] and g["default"] == "phone"
    g = grants.grant("a@example.com", "work", default=True)
    assert g["default"] == "work"


def test_revoke_clears_or_moves_default(store):
    grants.grant("a@example.com", "phone")
    grants.grant("a@example.com", "work")
    grants.grant("a@example.com", "mail")
    g = grants.revoke("a@example.com", "phone")       # was default; two remain
    assert g["default"] is None and g["channels"] == ["mail", "work"]
    g = grants.revoke("a@example.com", "mail")        # one remains: it is the default
    assert g == {"channels": ["work"], "default": "work"}
    g = grants.revoke("a@example.com", "nope")        # harmless
    assert g == {"channels": ["work"], "default": "work"}


def test_users_are_isolated(store):
    grants.grant("a@example.com", "phone")
    grants.grant("b@example.com", "work")
    assert grants.load("a@example.com")["channels"] == ["phone"]
    assert grants.load("b@example.com")["channels"] == ["work"]
    assert grants.load("c@example.com") == {"channels": [], "default": None}
