"""AlertsSDK: access rules, admin gating, and sending through Apprise."""

import pytest

from alerts.sdk import grants
from alerts.sdk.core import (
    AlertsError,
    AlertsSDK as sdk,
    ChannelNotAvailableError,
    ChannelsNotConfiguredError,
    NoDefaultChannelError,
    NotAnAdministratorError,
    UnknownChannelError,
)

CONFIG = "phone = capture://phone/\nwork = capture://work/\nboth = capture://b1/\nboth = capture://b2/\n"


# --- list_channels ------------------------------------------------------

def test_list_channels_unconfigured(as_user):
    as_user("a@example.com")
    with pytest.raises(ChannelsNotConfiguredError) as e:
        sdk.list_channels()
    assert "ALERTS_CHANNELS" in str(e.value)


def test_user_sees_only_granted_channels(as_user, channels_env):
    channels_env(CONFIG)
    as_user("a@example.com")
    grants.grant("a@example.com", "phone")
    out = sdk.list_channels()
    assert out == {
        "channels": [{"name": "phone", "services": ["Custom - capture"], "default": True}],
        "default": "phone",
    }
    assert "configured" not in out


def test_admin_also_sees_configured_and_invalid(as_user, channels_env, admin):
    channels_env(CONFIG + "broken = nosuch://x\n")
    admin("Admin@Example.com")
    as_user("admin@example.com")
    out = sdk.list_channels()
    assert out["channels"] == [] and out["default"] is None
    assert out["configured"] == ["both", "phone", "work"]
    assert out["invalid"] == {"broken": [5]}


def test_stdio_operator_has_every_channel(as_user, channels_env, stdio):
    channels_env(CONFIG)
    as_user("local")
    out = sdk.list_channels()
    assert [c["name"] for c in out["channels"]] == ["both", "phone", "work"]
    assert out["default"] is None               # three channels, none chosen
    grants.grant("local", "phone", default=True)
    assert sdk.list_channels()["default"] == "phone"


def test_stdio_single_channel_is_the_default(as_user, channels_env, stdio):
    channels_env("phone = capture://phone/\n")
    as_user("local")
    assert sdk.list_channels()["default"] == "phone"


# --- grants -------------------------------------------------------------

def test_grant_requires_admin(as_user, channels_env):
    channels_env(CONFIG)
    as_user("a@example.com")
    with pytest.raises(NotAnAdministratorError):
        sdk.grant_channel("b@example.com", "phone")
    with pytest.raises(NotAnAdministratorError):
        sdk.revoke_channel("b@example.com", "phone")


def test_admin_grants_and_revokes(as_user, channels_env, admin):
    channels_env(CONFIG)
    admin("admin@example.com")
    as_user("admin@example.com")
    assert sdk.grant_channel("B@Example.com", "phone") == {
        "email": "b@example.com", "channels": ["phone"], "default": "phone",
    }
    assert sdk.grant_channel("b@example.com", "work", default=True)["default"] == "work"
    assert sdk.revoke_channel("b@example.com", "work") == {
        "email": "b@example.com", "channels": ["phone"], "default": "phone",
    }


def test_grant_unknown_channel_refused(as_user, channels_env, admin):
    channels_env(CONFIG)
    admin("admin@example.com")
    as_user("admin@example.com")
    with pytest.raises(UnknownChannelError) as e:
        sdk.grant_channel("b@example.com", "pager")
    assert "both, phone, work" in str(e.value)


def test_stdio_operator_is_admin(as_user, channels_env, stdio):
    channels_env(CONFIG)
    as_user("local")
    assert sdk.grant_channel("local", "work", default=True)["default"] == "work"


# --- notify -------------------------------------------------------------

async def test_notify_default_channel_with_link(as_user, channels_env, sent):
    channels_env(CONFIG)
    as_user("a@example.com")
    grants.grant("a@example.com", "phone")
    out = await sdk.notify("Build finished.", link="https://example.com/session/1")
    assert out["sent"] is True and out["channel"] == "phone" and out["urgency"] == "normal"
    assert out["destinations"] == [{"service": "Custom - capture", "ok": True}]
    assert sent == [{
        "title": "Alert",
        "body": "Build finished.\n\nOpen the conversation to reply:\nhttps://example.com/session/1",
        "type": "warning",
        "host": "phone",
    }]


async def test_notify_urgency_maps_to_apprise_type(as_user, channels_env, sent):
    channels_env(CONFIG)
    as_user("a@example.com")
    grants.grant("a@example.com", "phone")
    await sdk.notify("fyi", urgency="low", title="Low")
    await sdk.notify("now", urgency="high", title="High")
    assert [(s["title"], s["type"]) for s in sent] == [("Low", "info"), ("High", "failure")]
    with pytest.raises(AlertsError):
        await sdk.notify("x", urgency="urgent")


async def test_notify_fans_out_to_every_destination(as_user, channels_env, sent):
    channels_env(CONFIG)
    as_user("a@example.com")
    grants.grant("a@example.com", "both")
    out = await sdk.notify("hi", channel="both")
    assert out["sent"] is True and len(out["destinations"]) == 2
    assert sorted(s["host"] for s in sent) == ["b1", "b2"]


async def test_notify_reports_a_failed_destination(as_user, channels_env, sent):
    channels_env("mixed = capture://ok/\nmixed = failing://bad/\n")
    as_user("a@example.com")
    grants.grant("a@example.com", "mixed")
    out = await sdk.notify("hi")
    assert out["sent"] is False
    by_service = {d["service"]: d for d in out["destinations"]}
    assert by_service["Custom - capture"]["ok"] is True
    assert by_service["Custom - failing"]["ok"] is False and "error" in by_service["Custom - failing"]


async def test_notify_refuses_ungranted_and_missing_default(as_user, channels_env, sent):
    channels_env(CONFIG)
    as_user("a@example.com")
    with pytest.raises(NoDefaultChannelError) as e:
        await sdk.notify("hi")
    assert "grant_channel" in str(e.value)
    grants.grant("a@example.com", "phone")
    grants.grant("a@example.com", "work")          # two channels, default still phone
    with pytest.raises(ChannelNotAvailableError) as e:
        await sdk.notify("hi", channel="both")
    assert "phone, work" in str(e.value)
    assert sent == []


async def test_notify_requires_a_message(as_user, channels_env, sent):
    channels_env(CONFIG)
    as_user("a@example.com")
    grants.grant("a@example.com", "phone")
    with pytest.raises(AlertsError):
        await sdk.notify("   ")


def test_list_channel_types(as_user):
    as_user("a@example.com")
    out = sdk.list_channel_types()
    assert {t["type"] for t in out["types"]} >= {"slack-webhook", "ntfy"}
