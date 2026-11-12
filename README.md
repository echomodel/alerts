# alerts

An MCP server that lets an AI agent push an alert to a person's phone, with a
link back to the conversation so the person can reply there. A long task
finished, a decision is needed, something failed: the agent calls `notify`,
the person's phone buzzes, a tap opens the conversation. Built on
[mcp-app](https://github.com/echomodel/mcp-app): the same binary runs locally
over stdio for one person or as a hosted multi-user service over HTTP, where
users sign in with the operator's identity provider.

Delivery is by [Apprise](https://github.com/caronc/apprise), so a channel can
be a Slack webhook, an ntfy topic, Pushover, Telegram, Discord, email and more.
Every channel is one-way: a reply typed in the notification app never reaches
the agent, and the link the alert carries is how the person gets back.

## Install

```bash
pipx install git+https://github.com/echomodel/alerts.git
```

| Command | What it does |
|---|---|
| `alerts-mcp` | The MCP server: `serve` (HTTP) and `stdio --user local`. |
| `alerts-admin` | Operator commands: `connect`, `users`, `health`, `probe`, `register`. |

Python 3.11 or newer.

## Configure channels

A **channel** is a name an agent sends to (`phone`, `work`). Behind each name
is one or more Apprise destination URLs, each carrying that service's
credential (the webhook, the topic, the SMTP login). Those URLs are the only
secret this server has, and they live in one of two places:

- the file `~/.config/alerts/channels` (`$XDG_CONFIG_HOME/alerts/channels`),
  for a local server;
- the `ALERTS_CHANNELS` environment variable, for a container, where the
  platform injects it from its secret store.

The variable wins when both exist. The content is the same: one destination
per line, `name = url`.

```
# ~/.config/alerts/channels   (chmod 600)
phone = https://hooks.slack.com/services/T.../B.../...
phone = ntfys://ntfy.sh/some-long-random-topic
work  = mailtos://user:password@smtp.example.com:587/?to=me@example.com
```

A name on several lines sends to every one of them; one line may carry
several comma-separated names. Lines Apprise rejects are reported by name in
`list_channels` (to an administrator), never by URL. The URL never appears in
a tool response, a log line, or the per-user store.

Setup guides, with every step and gotcha: [Slack webhook](docs/channels/slack-webhook.md)
(a Slack app's Incoming Webhook posting into its own DM, so Slack pushes it like
a message from someone else) and [ntfy](docs/channels/ntfy.md) (a topic the
ntfy phone app subscribes to; its own app, no account needed). The
`list_channel_types` tool lists every documented type with its URL form and
Apprise's documentation link.

## Run locally (stdio)

```bash
claude mcp add --scope user alerts -- alerts-mcp stdio --user local
agy mcp add alerts -- alerts-mcp stdio --user local
```

The stdio user is the operator: every configured channel is available to
them without a grant. With one channel configured it is the default; with
several, pick one once through the `grant_channel` tool:

```
grant_channel(email="local", channel="phone", default=true)
```

Then, from the agent:

```
notify(message="The import finished: 1,204 rows, 3 rejected. Shall I retry the rejects?",
       link="https://claude.ai/chat/...", urgency="normal")
```

Smoke test from a shell, without a client: start the server and send a
`tools/call` over stdio, or run `make test`, which covers the transport in
process.

## Tools

| Tool | Who | What |
|---|---|---|
| `notify(message, title?, channel?, link?, urgency?)` | any user | Send an alert to a channel (the user's default when omitted). `link` is the conversation URL; `urgency` is `low`, `normal` or `high`. |
| `list_channels()` | any user | The channels the caller can send to and their default. Administrators also see every configured channel and any invalid line. |
| `list_channel_types()` | any user | The documented destination types, their URL form, notes, and Apprise's docs link. |
| `grant_channel(email, channel, default?)` | administrators | Let a user send to a channel; optionally make it their default. |
| `revoke_channel(email, channel)` | administrators | Take a channel away from a user. |

The tool descriptions carry the full guidance an agent needs (when to alert,
what to put in the message, always pass the link). Refusals come back as
`{"error": ...}` naming the channels the caller may use.

Over HTTP a user may send only to channels an administrator granted them;
a user's first granted channel becomes their default. Over stdio the local
operator has every channel. mcp-app's own admin tools (`users_list`,
`user_register`, `user_block`, `usage_report`) are present too, visible to
administrators only.

## Deploy (HTTP)

The server is a standard Python web service. Any environment that can run
the container, set the variables in [Environment variables](#environment-variables),
and keep one directory across restarts can host it. This repo carries no
deployment-tool configuration: where and how a deployment runs belongs to
the operator's own deployment records.

- **Start command:** `alerts-mcp serve`, listening on `0.0.0.0:8080`
  (`--host`, `--port` to change). `PORT` is not read.
- **MCP endpoint:** `/` (root). **Health:** `GET /health`, no auth.
  **Discovery:** `GET /.well-known/oauth-protected-resource`, no auth.
- **Auth:** standard MCP OAuth. The server validates the identity
  provider's tokens itself; the platform must let unauthenticated traffic
  through to the app and forward `Host` unchanged.
- **Storage:** one directory (`APP_USERS_PATH`) that survives restarts.
- **Secrets:** only `ALERTS_CHANNELS`. Inject it from the platform's secret
  store, never from the repo or an image.

### Docker

```bash
docker build -t alerts .
docker run -p 8080:8080 \
  -e AUTH_ISSUER=https://login.example.com/ \
  -e ADMIN_EMAILS=you@example.com \
  -e ALERTS_CHANNELS="$(cat ~/.config/alerts/channels)" \
  -v /persistent/path:/data -e APP_USERS_PATH=/data/users \
  alerts
```

Any container platform (Cloud Run, Fly, Render, Kubernetes, a VM with
systemd) takes the same image and the same variables, set its own way.

### Identity provider

Once per deployment, at the identity provider:

1. An API (resource) whose identifier is the server's public URL, exactly as
   users will type it, trailing slash included; refresh tokens allowed.
2. The sign-in method users should see (Sign in with Google is a common choice).
3. Client identification from the server URL alone: client ID metadata
   documents where supported, else dynamic client registration.
4. The user's email in access tokens; if the issuer namespaces custom claims,
   set `AUTH_EMAIL_CLAIM` to the full claim name.
5. Default user-delegated access for third-party clients, if the issuer
   treats dynamically registered clients as third party.

An MCP client then needs only the URL: it discovers the issuer, signs the
user in, and holds the token. Nothing is pasted anywhere.

## Environment variables

Every variable the server reads. The table is for scanning; the reference
below it has the format, an example, and what happens when a value is
missing or wrong. All are read once, at startup: a change needs a restart.

| Variable | Applies to | Required | Type | Default when unset | Secret |
|---|---|---|---|---|---|
| `AUTH_ISSUER` | HTTP | yes | URL | none: startup fails | no |
| `ADMIN_EMAILS` | HTTP | yes, to administer | list of emails | none: no administrators | no |
| `ALERTS_CHANNELS` | both | yes, unless the channels file exists | multi-line text | the channels file | **yes** |
| `APP_USERS_PATH` | both | yes, for durable data | directory path | `$XDG_DATA_HOME/alerts/users` | no |
| `REQUIRED_FS_TYPE` | both | recommended | list of filesystem types | no check | no |
| `AUTH_EMAIL_CLAIM` | HTTP | if the issuer namespaces it | claim name | `email` | no |
| `AUTH_ADMISSION` | HTTP | no | enum: `allowlist`, `open` | `allowlist` | no |
| `MAX_USERS` | HTTP | no | integer ≥ 1 | unlimited | no |
| `AUTH_AUDIENCE` | HTTP | no | URL | derived from the request's `Host` | no |
| `AUTH_JWKS_URI` | HTTP | no | URL | OpenID discovery from the issuer | no |
| `ADMIN_CLIENT_IDS` | HTTP | no | list of client ids | none | no |
| `USAGE_FLUSH_SECONDS` | HTTP | no | integer, seconds | `60` | no |
| `XDG_CONFIG_HOME` | both | no | directory path | `~/.config` | no |
| `XDG_DATA_HOME` | both | no | directory path | `~/.local/share` | no |

Lists are comma-separated; spaces around items are ignored.

### Variable reference

**`AUTH_ISSUER`** — the identity provider that issues access tokens.
- Format: the issuer URL exactly as in the token's `iss` claim, trailing
  slash included if the issuer uses one. Example: `https://login.example.com/`.
- Missing: `alerts-mcp serve` refuses to start, naming the variable. stdio
  ignores it.
- Wrong: every request after sign-in gets `401`. The startup line
  `mcp_app.startup auth issuer=...` shows the value in use; a missing or
  extra trailing slash is the usual mistake.

**`ADMIN_EMAILS`** — who administers this deployment.
- Format: comma-separated emails, compared lower-cased. Example:
  `you@example.com,ops@example.com`.
- Effect: each email is admitted on first sign-in, sees the admin tools
  (`grant_channel`, `revoke_channel`, `users_list`, `user_register`,
  `user_block`, `usage_report`), and may call `/admin`.
- Missing: the server serves registered users but nobody can administer it
  or bootstrap the first user; startup logs a warning. Changing the list is
  a restart.

**`ALERTS_CHANNELS`** — the channel definitions, the server's only secret.
- Format: one destination per line, `name = apprise-url`; several
  comma-separated names may share a line, and a name on several lines sends
  to all of them. Blank lines and `#` comments are ignored. See
  [Configure channels](#configure-channels).
- Precedence: when set and non-empty it replaces the channels file
  (`$XDG_CONFIG_HOME/alerts/channels`) entirely.
- Missing (and no file): every tool answers that no channels are
  configured; nothing fails at startup.
- Wrong: a line Apprise rejects is skipped and reported to administrators
  by channel name and line number in `list_channels`, never by URL.
- Handling: inject from a secret store; it carries every destination's
  credential. Rotate by replacing a line and restarting.

**`APP_USERS_PATH`** — where per-user records (admission state, grants)
and usage counters live.
- Format: a directory path; created if missing.
- Default: `$XDG_DATA_HOME/alerts/users`, which in a container is the
  image's filesystem and is lost on restart. Point it at a mounted volume
  for any real deployment.

**`REQUIRED_FS_TYPE`** — a startup guard that the data directory is on the
storage you meant.
- Format: comma-separated filesystem types, matched on `.` boundaries
  (`fuse` matches `fuse.gcsfuse`). Examples: `fuse`, `nfs`, `ext4,xfs`.
- Effect: if `APP_USERS_PATH` is missing, unwritable, or on another
  filesystem type, the process exits non-zero instead of serving with data
  that would vanish. Unset: no check; `/health` then reports storage
  `unverified` and status `degraded`.

**`AUTH_EMAIL_CLAIM`** — the access-token claim carrying the user's email.
- Format: a claim name. Issuers that refuse standard claim names in access
  tokens need the full namespaced name, e.g. `https://example.com/email`.
- Wrong: signed-in users get `401` (no email in the token).

**`AUTH_ADMISSION`** — who besides `ADMIN_EMAILS` gets in on first sign-in.
- Values: `allowlist` (default): only emails an administrator registered
  with `user_register`; anyone else is parked `pending` with a `403`.
  `open`: any email the issuer vouches for is approved, up to `MAX_USERS`.
- Note: open admission still gives a new user no channels; an
  administrator grants them with `grant_channel`.

**`MAX_USERS`** — cap on user records sign-in may create.
- Format: a positive integer. Unset: unlimited. Anything else: startup
  fails naming the value. Administrators are never counted out.

**`AUTH_AUDIENCE`** — pins the audience a token must carry.
- Default: the URL the request arrived at, from `Host`. Set it only when
  the server is reached by IP address or under several hostnames.

**`AUTH_JWKS_URI`** — where the issuer's signing keys are.
- Default: found by OpenID discovery from `AUTH_ISSUER`. Set it only for an
  issuer without discovery.

**`ADMIN_CLIENT_IDS`** — machine clients treated as administrators.
- Format: comma-separated client ids from client-credentials tokens. For
  scripts that call the admin tools; the principal is `client:<id>`.

**`USAGE_FLUSH_SECONDS`** — how often tool-call counters reach the data
directory.
- Format: integer seconds. Default `60`. stdio flushes after every call.

**`XDG_CONFIG_HOME`, `XDG_DATA_HOME`** — the standard base directories.
- They place the channels file (`$XDG_CONFIG_HOME/alerts/channels`), the
  admin CLI's saved target (`$XDG_CONFIG_HOME/alerts/setup.json`), and the
  default data directory. Rarely set by hand.

Not read: `PORT` (use `--port`) and any log-level variable.

## Connect the admin CLI

After a deploy, point the admin CLI at it. `connect` takes the URL and
nothing else: the server holds no secret and the identity provider does the
sign-in. The target is saved in `~/.config/alerts/setup.json`, so later
commands take no URL. Deploying never connects the CLI; do it explicitly.

```bash
alerts-admin connect https://alerts.example.com
alerts-admin probe
alerts-admin register
alerts-admin connect local      # switch to the local store; the remote stays saved
alerts-admin connect remote     # and back
```

Against a deployment, `health`, `probe` and `register` work without signing
in. `users`, `tools` and `safe-tool` need a signed-in administrator, which
the CLI cannot do yet; against a remote they exit saying so. Users on a
deployment are managed through the admin MCP tools below, from an
administrator's own MCP client.

## Manage users and grants

Who gets in: every `ADMIN_EMAILS` entry on first sign-in, and every user an
administrator registered. Anyone else who signs in is parked `pending` with a
403 until approved. From an administrator's MCP client:

```
users_list()                                   # pending first, then approved, blocked
user_register("alice@example.com")             # approve, in advance or after a pending sign-in
grant_channel("alice@example.com", "phone")    # her first channel is also her default
grant_channel("alice@example.com", "work", default=true)
revoke_channel("alice@example.com", "work")
user_block("bob@example.com")                  # refuse from now on; data stays
```

A registered user with no grant can sign in and list channels, and `notify`
tells them to ask an administrator. The administrator's own first use is the
same two steps: sign in, then `grant_channel` for their own email.

### Rotating a channel credential

A credential lives only in the channel definitions. Replace the line
(`~/.config/alerts/channels` locally; the platform's secret store and a
restart for a deployment). Grants refer to
the channel by name, so nothing else changes. When a webhook or topic leaks,
revoke it at the service first, then replace the line.

Locally, `alerts-admin connect local` then `alerts-admin users list` shows
the local store; grants for the `local` user are set through `grant_channel`
over stdio.

## Sanity-check the deployment

```bash
alerts-admin probe
```

reports `Health: healthy` (or `degraded`) and `OAuth: ok` with the issuer
and the `resource` URL. The issuer must be the identity provider you set;
the resource must be the URL users type (a different scheme or host means
the front door rewrites `Host`; fix the proxy or pin `AUTH_AUDIENCE`). Then
the end-to-end proof: add the URL in your own MCP client, sign in, call
`list_channels`, grant yourself a channel, and `notify` yourself with a
link. The phone should buzz and the tap should land in the conversation.

## Connect end users

```bash
alerts-admin register
```

prints the registration command for each client. No command carries a
credential, so the same output serves every user:

```bash
claude mcp add --transport http -s user alerts https://alerts.example.com/
agy mcp add alerts https://alerts.example.com/
# Claude.ai and Claude mobile: Settings > Connectors > Add custom connector
https://alerts.example.com/
```

Each client signs the user in with the identity provider on first use. A
user whose email is not registered gets a 403 until an administrator runs
`user_register`; then `grant_channel` gives them somewhere to send.

## Usage report

An administrator asks the connector for `usage_report(week="current")` or
`"prior"`: users (total, new, active), tool calls (total, errors, per tool)
and the most active users with masked emails. Non-administrators never see
the tool.

## Files

| Path | Purpose |
|---|---|
| `$XDG_CONFIG_HOME/alerts/channels` | Channel definitions for a local server; `ALERTS_CHANNELS` overrides it. |
| `$APP_USERS_PATH/<user>/` | Per-user store: admission record and `grants.json`. |
| `$XDG_CONFIG_HOME/alerts/setup.json` | The admin CLI's saved `connect` target. |

Variables are in [Environment variables](#environment-variables).

`urgency` maps to Apprise's notification type: `low` to info, `normal` to
warning, `high` to failure. Services that colour or tag by type show it
(Slack: blue, orange, red); ntfy does not. A `link` is appended to the
message body as a plain URL on its own line, which phones render as a
tappable link.

## Further reading

- [Slack webhook channel](docs/channels/slack-webhook.md): create the Slack
  app, turn on Incoming Webhooks, aim it at the app's own DM, and the phone
  notification settings that make it buzz.
- [ntfy channel](docs/channels/ntfy.md): pick a topic, subscribe the phone
  app, self-host or use ntfy.sh, and what the priority settings do.
- [CONTRIBUTING.md](CONTRIBUTING.md): architecture, the rules that keep
  credentials out of responses, tests, releases.
- Built on [mcp-app](https://github.com/echomodel/mcp-app); delivery by
  [Apprise](https://github.com/caronc/apprise).

## For agents: optional skill accelerant

If you are a coding agent that supports skills, the
[mcp-app skill](https://github.com/echomodel/mcp-app/tree/main/skills/mcp-app)
provides step-by-step workflows for authoring and operating apps on this
framework. It is optional; this README is self-sufficient.
