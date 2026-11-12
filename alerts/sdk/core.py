"""The alerts SDK: everything the tools do.

``AlertsSDK`` is stateless and used as a namespace of classmethods. It reads
the caller from mcp-app's ``current_user`` and the destinations from
``channels``; the only state it writes is a user's grants.
"""

from __future__ import annotations

import asyncio
import logging

import apprise
from mcp_app import is_stdio
from mcp_app.auth import is_admin
from mcp_app.context import current_user

from alerts.sdk import channels as channel_config
from alerts.sdk import grants as grant_store

logger = logging.getLogger("alerts")

# Urgency as an agent states it, mapped to the Apprise notification type that
# services colour or tag by (Slack: blue / orange / red). Services without a
# per-message type (ntfy) show no difference.
URGENCIES: dict[str, apprise.NotifyType] = {
    "low": apprise.NotifyType.INFO,
    "normal": apprise.NotifyType.WARNING,
    "high": apprise.NotifyType.FAILURE,
}
DEFAULT_TITLE = "Alert"
SEND_TIMEOUT_SECONDS = 20.0


class AlertsError(Exception):
    """A refusal the caller can act on; the message states what and why."""


class ChannelsNotConfiguredError(AlertsError):
    def __init__(self):
        super().__init__(
            "No channels are configured on this server: set the ALERTS_CHANNELS "
            f"environment variable or create {channel_config.config_path()} "
            "(one 'name = url' line per destination; the operator does this, not an agent)."
        )


class UnknownChannelError(AlertsError):
    def __init__(self, channel: str, known: list[str]):
        super().__init__(
            f"'{channel}' is not a configured channel. Configured: {', '.join(known) or 'none'}."
        )


class ChannelNotAvailableError(AlertsError):
    def __init__(self, channel: str, available: list[str]):
        super().__init__(
            f"'{channel}' is not a channel you can send to. "
            f"Yours: {', '.join(available) or 'none'}. "
            "An administrator grants channels with grant_channel."
        )


class NoDefaultChannelError(AlertsError):
    def __init__(self, available: list[str]):
        if available:
            msg = (
                "No default channel: pass channel= explicitly. "
                f"Yours: {', '.join(available)}."
            )
        else:
            msg = (
                "You have no channels. An administrator grants one with "
                "grant_channel(email, channel, default=True)."
            )
        super().__init__(msg)


class NotAnAdministratorError(AlertsError):
    def __init__(self):
        super().__init__("Administrators only (an email in ADMIN_EMAILS, or the local stdio operator).")


class AlertsSDK:
    """All behaviour. Tools call ``sdk.<method>()`` and nothing else."""

    # --- who is calling -------------------------------------------------

    @classmethod
    def caller(cls) -> str:
        return current_user.get().email

    @classmethod
    def caller_is_admin(cls) -> bool:
        """The local stdio operator, or an ``ADMIN_EMAILS`` entry over HTTP."""
        return is_stdio() or is_admin(cls.caller())

    @classmethod
    def require_admin(cls) -> None:
        if not cls.caller_is_admin():
            raise NotAnAdministratorError()

    # --- channels -------------------------------------------------------

    @classmethod
    def configured(cls) -> channel_config.Channels:
        loaded = channel_config.load()
        if loaded is None:
            raise ChannelsNotConfiguredError()
        return loaded

    @classmethod
    def available(cls, email: str, configured: channel_config.Channels) -> tuple[list[str], str | None]:
        """The channel names ``email`` may send to, and their default.

        Over stdio the local user is the operator and has every configured
        channel. Over HTTP a user has the channels granted to them. Either
        way the default is the user's granted default, or the single
        available channel when there is exactly one.
        """
        names = configured.names()
        g = grant_store.load(email)
        if is_stdio():
            available = names
        else:
            available = [n for n in g["channels"] if n in names]
        default = g["default"] if g["default"] in available else None
        if default is None and len(available) == 1:
            default = available[0]
        return available, default

    @classmethod
    def list_channels(cls) -> dict:
        configured = cls.configured()
        available, default = cls.available(cls.caller(), configured)
        out = {
            "channels": [
                {"name": n, "services": configured.services(n), "default": n == default}
                for n in available
            ],
            "default": default,
        }
        if cls.caller_is_admin():
            out["configured"] = configured.names()
            if configured.invalid:
                out["invalid"] = {n: lines for n, lines in configured.invalid.items()}
            if configured.unnamed:
                out["unnamed_destinations"] = configured.unnamed
        return out

    @classmethod
    def list_channel_types(cls) -> dict:
        return {"types": channel_config.channel_types()}

    # --- grants (administrators) ---------------------------------------

    @classmethod
    def grant_channel(cls, email: str, channel: str, default: bool = False) -> dict:
        cls.require_admin()
        configured = cls.configured()
        if channel not in configured.names():
            raise UnknownChannelError(channel, configured.names())
        email = email.strip().lower()
        g = grant_store.grant(email, channel, default=default)
        return {"email": email, **g}

    @classmethod
    def revoke_channel(cls, email: str, channel: str) -> dict:
        cls.require_admin()
        email = email.strip().lower()
        g = grant_store.revoke(email, channel)
        return {"email": email, **g}

    # --- sending --------------------------------------------------------

    @classmethod
    def compose(cls, message: str, link: str | None) -> str:
        body = message.strip()
        if link:
            body += f"\n\nOpen the conversation to reply:\n{link.strip()}"
        return body

    @classmethod
    async def notify(
        cls,
        message: str,
        title: str | None = None,
        channel: str | None = None,
        link: str | None = None,
        urgency: str = "normal",
    ) -> dict:
        if urgency not in URGENCIES:
            raise AlertsError(f"urgency must be one of {', '.join(URGENCIES)}; got '{urgency}'.")
        if not message or not message.strip():
            raise AlertsError("message is required.")
        configured = cls.configured()
        available, default = cls.available(cls.caller(), configured)
        if channel is None:
            if default is None:
                raise NoDefaultChannelError(available)
            channel = default
        if channel not in available:
            raise ChannelNotAvailableError(channel, available)
        servers = configured.servers.get(channel, [])
        if not servers:
            raise AlertsError(f"Channel '{channel}' has no valid destination; check its line in the channel config.")

        title = (title or DEFAULT_TITLE).strip()
        body = cls.compose(message, link)
        notify_type = URGENCIES[urgency]

        async def send(server) -> dict:
            result = {"service": server.service_name, "ok": False}
            try:
                ok = await asyncio.wait_for(
                    server.async_notify(
                        body=body, title=title, notify_type=notify_type,
                        body_format=apprise.NotifyFormat.TEXT,
                    ),
                    timeout=SEND_TIMEOUT_SECONDS,
                )
                result["ok"] = bool(ok)
                if not ok:
                    result["error"] = "the service refused or did not acknowledge the message"
            except asyncio.TimeoutError:
                result["error"] = f"no answer within {SEND_TIMEOUT_SECONDS:.0f}s"
            except Exception as exc:  # the plugin's failure, never its URL
                logger.warning("send to %s via %s failed: %s", channel, server.service_name, type(exc).__name__)
                result["error"] = f"{type(exc).__name__}: {exc}"
            return result

        destinations = await asyncio.gather(*(send(s) for s in servers))
        return {
            "sent": all(d["ok"] for d in destinations),
            "channel": channel,
            "title": title,
            "urgency": urgency,
            "destinations": list(destinations),
        }
