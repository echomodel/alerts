"""Channel configuration: where the destinations come from and how they load.

A *channel* is a name an agent can send to. Behind each name is one or more
Apprise destination URLs, each of which carries the credential for that
service (a Slack webhook, an ntfy topic, an SMTP login). The URLs are the
secret of this server, so they live in exactly two places and nowhere else:

* the ``ALERTS_CHANNELS`` environment variable, for containers, where the
  platform injects it from its secret store; or
* the file ``$XDG_CONFIG_HOME/alerts/channels`` (``~/.config/alerts/channels``
  by default), for a local stdio server.

The environment variable wins when both are present. The content is the
same in both: one destination per line, ``name = apprise-url``. Blank lines
and ``#`` comments are ignored. A name may appear on several lines (every
listed destination receives the alert), and a line may carry several names
separated by commas.

Nothing in this module returns, logs, or stores a URL. Callers see channel
names and Apprise service names (``Slack``, ``ntfy``) only.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import apprise

ENV_CHANNELS = "ALERTS_CHANNELS"
CONFIG_FILE_NAME = "channels"


def config_path() -> Path:
    """The channels file for a local server: ``$XDG_CONFIG_HOME/alerts/channels``."""
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return xdg / "alerts" / CONFIG_FILE_NAME


def load_text() -> tuple[str, str] | None:
    """The raw channel definitions and where they came from.

    Returns ``(text, source)`` where ``source`` is ``"env"`` or the file
    path, or ``None`` when neither the variable nor the file is present.
    """
    text = os.environ.get(ENV_CHANNELS)
    if text is not None and text.strip():
        return text, "env"
    path = config_path()
    if path.is_file():
        return path.read_text(), str(path)
    return None


@dataclass
class Definition:
    """One parsed line: the names on the left, the URL on the right."""

    names: list[str]
    url: str
    line: int


@dataclass
class Channels:
    """The configured destinations, grouped by channel name.

    ``servers`` maps a channel name to its Apprise plugin instances;
    ``invalid`` lists channel names whose line Apprise rejected (the URL
    itself is never kept); ``unnamed`` counts lines with a URL but no name.
    """

    servers: dict[str, list] = field(default_factory=dict)
    invalid: dict[str, list[int]] = field(default_factory=dict)
    unnamed: int = 0
    source: str | None = None

    def names(self) -> list[str]:
        return sorted(self.servers)

    def services(self, name: str) -> list[str]:
        return [s.service_name for s in self.servers.get(name, [])]


def parse(text: str) -> list[Definition]:
    """Split ``name = url`` lines; names may be comma-separated."""
    out: list[Definition] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and "://" not in line.split("=", 1)[0]:
            left, url = line.split("=", 1)
            names = [n.strip() for n in left.replace(",", " ").split() if n.strip()]
        else:
            names, url = [], line
        out.append(Definition(names=names, url=url.strip(), line=number))
    return out


def build(text: str, source: str | None = None) -> Channels:
    """Instantiate the Apprise plugin for every definition, keyed by channel."""
    channels = Channels(source=source)
    for d in parse(text):
        if not d.names:
            channels.unnamed += 1
            continue
        probe = apprise.Apprise()
        if not probe.add(d.url, tag=d.names):
            for n in d.names:
                channels.invalid.setdefault(n, []).append(d.line)
            continue
        for server in probe:
            for n in d.names:
                channels.servers.setdefault(n, []).append(server)
    return channels


def load() -> Channels | None:
    """Load and build the configured channels, or ``None`` when unconfigured."""
    loaded = load_text()
    if loaded is None:
        return None
    text, source = loaded
    return build(text, source)


# --- channel types ---------------------------------------------------------

# The destination services this server documents. Each entry names the
# Apprise service (for its documentation link), the URL shape an operator
# writes in the channels file, and what to know before choosing it.
# Every one of them is one-way: a reply typed in the app never reaches the
# agent; the ``link`` an alert carries is how the person gets back.
CHANNEL_TYPES: list[dict] = [
    {
        "type": "slack-webhook",
        "service": "Slack",
        "url_form": "https://hooks.slack.com/services/T.../B.../...",
        "notes": "An Incoming Webhook of a Slack app. Point it at the app's own DM so Slack "
                 "pushes it like a message from someone else. Paste the webhook URL as is.",
        "guide": "docs/channels/slack-webhook.md",
    },
    {
        "type": "ntfy",
        "service": "ntfy",
        "url_form": "ntfys://ntfy.sh/<topic>  or  ntfys://<user>:<password>@<host>/<topic>",
        "notes": "A topic on ntfy.sh or a self-hosted ntfy server; the ntfy phone app subscribes "
                 "to it. Treat the topic name as a secret on the public server.",
        "guide": "docs/channels/ntfy.md",
    },
    {
        "type": "pushover",
        "service": "Pushover",
        "url_form": "pover://<user-key>@<app-token>",
        "notes": "Pushover's own phone app; one-time purchase per platform.",
    },
    {
        "type": "telegram",
        "service": "Telegram",
        "url_form": "tgram://<bot-token>/<chat-id>",
        "notes": "A Telegram bot messaging a chat it has been added to.",
    },
    {
        "type": "discord",
        "service": "Discord",
        "url_form": "discord://<webhook-id>/<webhook-token>",
        "notes": "A Discord channel webhook.",
    },
    {
        "type": "email",
        "service": "E-Mail",
        "url_form": "mailtos://<user>:<password>@<smtp-host>:587/?to=<address>",
        "notes": "SMTP. Use port 587 or 465: cloud platforms generally block outbound port 25.",
    },
    {
        "type": "gotify",
        "service": "Gotify",
        "url_form": "gotifys://<host>/<app-token>",
        "notes": "A self-hosted Gotify server and its phone app.",
    },
    {
        "type": "matrix",
        "service": "Matrix",
        "url_form": "matrixs://<user>:<password>@<host>/#<room>",
        "notes": "A Matrix room, via a user or an access token.",
    },
]


def channel_types() -> list[dict]:
    """The documented destination types, with Apprise's documentation link for each."""
    details = {s["service_name"]: s for s in apprise.Apprise().details()["schemas"]}
    out = []
    for entry in CHANNEL_TYPES:
        info = details.get(entry["service"], {})
        out.append({
            **entry,
            "schemes": list(info.get("protocols") or ()) + list(info.get("secure_protocols") or ()),
            "apprise_docs": info.get("setup_url"),
            "receives_replies": False,
        })
    return out
