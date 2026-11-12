"""MCP tools: plain async functions, discovered by mcp-app.

Name becomes the tool name, docstring the description, type hints the
schema. Each tool calls one SDK method and turns a refusal into a plain
``{"error": ...}`` so the agent reads what to do next.
"""

from __future__ import annotations

from alerts.sdk.core import AlertsError, AlertsSDK

sdk = AlertsSDK


async def notify(
    message: str,
    title: str | None = None,
    channel: str | None = None,
    link: str | None = None,
    urgency: str = "normal",
) -> dict:
    """Push an alert to a person's phone (or other destination) and say how to get back to you.

    Use it when a person is not watching and should be: a long task finished,
    a decision is needed before you can continue, something failed. Do not
    use it for progress updates or anything the person will see when they
    return anyway. One alert per event; never repeat an unanswered one.

    Always pass `link`: the URL of this conversation or session, so a tap on
    the alert returns the person here to reply. Alerts are one-way; a reply
    typed in the notification app never reaches you.

    Args:
        message: What happened and what you need, in one to three sentences.
            Plain text (phones show no markup). Say what you will do if there
            is no answer.
        title: Short subject shown as the notification heading. Default "Alert".
        channel: Which channel to send to, by name from `list_channels`.
            Omit it to use your default channel.
        link: URL of the conversation or session to return to. Include it.
        urgency: "low" (FYI), "normal" (default; needs the person soon), or
            "high" (needs them now, or something is broken). Channels colour
            or tag the alert by it.

    Returns {"sent": bool, "channel", "title", "urgency", "destinations":
    [{"service", "ok", "error"?}]}. "sent" is true only when every destination
    behind the channel accepted the message. A refusal comes back as
    {"error": "..."} naming the channels you can use.
    """
    try:
        return await sdk.notify(message, title=title, channel=channel, link=link, urgency=urgency)
    except AlertsError as e:
        return {"error": str(e)}


async def list_channels() -> dict:
    """List the alert channels you can send to, and which one is your default.

    Each channel is a name backed by one or more destinations (shown by
    service, such as "Slack" or "ntfy"; credentials are never shown). Call
    it before `notify` when you are unsure which channel to use, or when
    `notify` refuses a channel name.

    Returns {"channels": [{"name", "services", "default"}], "default"}. For an
    administrator it also lists every configured channel ("configured") and
    any whose configuration line is invalid ("invalid").
    """
    try:
        return sdk.list_channels()
    except AlertsError as e:
        return {"error": str(e)}


async def list_channel_types() -> dict:
    """List the kinds of destination this server can deliver to, and how each is configured.

    For an operator deciding what to set up, or an agent asked "what can
    alerts go to?". Each type has the URL form the operator writes in the
    server's channel configuration, notes on its limits, and a link to the
    Apprise documentation for that service. Every type is one-way: replies
    typed in the destination app do not reach the agent.
    """
    return sdk.list_channel_types()


async def grant_channel(email: str, channel: str, default: bool = False) -> dict:
    """Administrators only: let a user send to a channel, optionally as their default.

    A user can send to the channels granted to them and nothing else; the
    local stdio operator has every configured channel without a grant. A
    user's first granted channel becomes their default automatically; pass
    `default=true` to make another one the default. Granting an already
    granted channel is harmless.

    Args:
        email: The user's email as the identity provider reports it (or
            "local" for the stdio user).
        channel: A configured channel name (see `list_channels`).
        default: Make this the user's default channel for `notify`.

    Returns the user's grants: {"email", "channels": [...], "default"}.
    """
    try:
        return sdk.grant_channel(email, channel, default=default)
    except AlertsError as e:
        return {"error": str(e)}


async def revoke_channel(email: str, channel: str) -> dict:
    """Administrators only: stop a user from sending to a channel.

    Removes the grant; if it was the user's default, the default clears (or
    moves to their only remaining channel). The channel's configuration is
    untouched. Revoking a channel the user does not have is harmless.

    Args:
        email: The user's email as the identity provider reports it.
        channel: The channel name to remove.

    Returns the user's remaining grants: {"email", "channels": [...], "default"}.
    """
    try:
        return sdk.revoke_channel(email, channel)
    except AlertsError as e:
        return {"error": str(e)}
