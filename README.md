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

The server is a standard Python web service. Any environment that can run a
container and supply the variables below can host it.

### Runtime contract

| Variable | Required | If missing | Purpose |
|---|---|---|---|
| `AUTH_ISSUER` | yes | startup fails | The identity provider's issuer URL, exactly as it appears in the token's `iss` claim (trailing slash included if the issuer uses one). |
| `ADMIN_EMAILS` | yes | nobody can administer | Comma-separated emails of the administrators. Each is admitted on first sign-in and sees the admin tools. |
| `AUTH_EMAIL_CLAIM` | if the issuer namespaces it | `email` | The access-token claim carrying the user's email. |
| `ALERTS_CHANNELS` | yes | every tool reports "no channels configured" | The channel definitions (the `name = url` lines), from the platform's secret store. |
| `APP_USERS_PATH` | yes, for durable data | `~/.local/share/alerts/users/` | Per-user data (grants, admission state). Must be persistent storage: the container filesystem loses it on restart. |
| `REQUIRED_FS_TYPE` | recommended | no check | Filesystem type the data directory must be on (`fuse` for a mounted bucket); startup fails if the volume is missing instead of silently losing data. |
| `AUTH_AUDIENCE` | no | derived from `Host` | Pin the token audience when the service is reached by address or on several hostnames. |

- Start command: `alerts-mcp serve` (default `0.0.0.0:8080`).
- MCP endpoint: `/` (root). Health: `GET /health`, no auth. Discovery:
  `GET /.well-known/oauth-protected-resource`, no auth.
- Auth: standard MCP OAuth. The server validates the identity provider's
  tokens itself; the platform must pass unauthenticated traffic through and
  forward `Host` unchanged.

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

### Google Cloud Run with gapp

The repo carries a [gapp](https://github.com/echomodel/gapp) manifest,
`gapp.yaml`: the Dockerfile is built as is, user data goes on a mounted
bucket at `APP_USERS_PATH` with `REQUIRED_FS_TYPE=fuse`, and three values
come from Secret Manager, set once per deployment: `channels` (the channel
lines), `auth-issuer` and `admin-emails`. The last two are not secrets to
the server, but they name one deployment's tenant and administrators, and
Secret Manager is gapp's channel for operator-supplied values that must not
sit in a public repo. `AUTH_EMAIL_CLAIM` is a plain value in the manifest.
The custom domain is set on the deployment with `gapp ci setup --domain`,
never in the manifest.

```bash
gapp secrets set auth-issuer         # https://<tenant>/  (trailing slash)
gapp secrets set admin-emails        # you@example.com
gapp secrets set channels            # the channel lines; or --from-stdin
gapp ci setup alerts --repo echomodel/alerts --project <project-id> --domain mcp.alerts.example.com
gapp ci deploy alerts                # or dispatch the fleet's gapp-deploy workflow
gapp ci status alerts --live         # URL and health
```

Changing any of the three means `gapp secrets set` again and a redeploy:
the variables are read when the container starts.

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
(`~/.config/alerts/channels` locally; `gapp secrets set channels` and a
redeploy, or the platform's equivalent, for a deployment). Grants refer to
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

## Configuration reference

| Path or variable | Purpose |
|---|---|
| `~/.config/alerts/channels` | Channel definitions for a local server (`$XDG_CONFIG_HOME/alerts/channels`). |
| `ALERTS_CHANNELS` | Channel definitions for a container; overrides the file. |
| `<APP_USERS_PATH>/<user>/` | Per-user store: admission record and `grants.json` (`APP_USERS_PATH` overrides). |
| `~/.config/alerts/setup.json` | The admin CLI's saved `connect` target. |
| `AUTH_ISSUER`, `ADMIN_EMAILS`, `AUTH_EMAIL_CLAIM`, `AUTH_AUDIENCE`, `AUTH_ADMISSION`, `MAX_USERS`, `REQUIRED_FS_TYPE` | mcp-app's HTTP settings; see the runtime contract above and the mcp-app README for admission policy. |

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
