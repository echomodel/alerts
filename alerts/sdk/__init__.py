"""The alerts SDK: channel configuration, per-user grants, and sending.

Everything the MCP tools do lives here; the tools are one-line wrappers.
"""

from alerts.sdk.core import (
    AlertsError,
    AlertsSDK,
    ChannelNotAvailableError,
    ChannelsNotConfiguredError,
    NoDefaultChannelError,
    NotAnAdministratorError,
    UnknownChannelError,
    URGENCIES,
)

__all__ = [
    "AlertsError",
    "AlertsSDK",
    "ChannelNotAvailableError",
    "ChannelsNotConfiguredError",
    "NoDefaultChannelError",
    "NotAnAdministratorError",
    "UnknownChannelError",
    "URGENCIES",
]
