"""Who may send to which channel.

A grant is per user and lives in mcp-app's per-user store under the key
``grants``: ``{"channels": [...names...], "default": name-or-null}``. The
channels themselves (and their credentials) are not here; see ``channels``.
"""

from __future__ import annotations

import mcp_app

KEY = "grants"


def load(email: str) -> dict:
    data = mcp_app.get_store().load(email, KEY) or {}
    channels = sorted({c for c in data.get("channels", []) if isinstance(c, str)})
    default = data.get("default")
    if default not in channels:
        # One channel needs no choosing; otherwise there is no default until set.
        default = channels[0] if len(channels) == 1 else None
    return {"channels": channels, "default": default}


def save(email: str, grants: dict) -> None:
    mcp_app.get_store().save(email, KEY, grants)


def grant(email: str, channel: str, default: bool = False) -> dict:
    g = load(email)
    if channel not in g["channels"]:
        g["channels"] = sorted(g["channels"] + [channel])
    if default:
        g["default"] = channel
    save(email, g)
    return load(email)


def revoke(email: str, channel: str) -> dict:
    g = load(email)
    g["channels"] = [c for c in g["channels"] if c != channel]
    if g["default"] == channel:
        g["default"] = None
    save(email, g)
    return load(email)
