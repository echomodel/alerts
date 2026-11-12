# Contributing

## Project structure

```
alerts/
├── README.md               # Users and operators: install, channels, run, deploy, administer.
├── CONTRIBUTING.md         # This file: architecture, rules to preserve, tests, releases.
├── pyproject.toml          # Package, entry points, mcp-app pin, pytest config.
├── Dockerfile              # Container build: the one deployment artifact the repo carries.
├── alerts/
│   ├── __init__.py         # The App: name, tools module, SDK package. No profile model.
│   ├── sdk/
│   │   ├── channels.py     # Channel definitions: env var or file, parsing, Apprise instances, type table.
│   │   ├── grants.py       # Per-user grants in mcp-app's store.
│   │   └── core.py         # AlertsSDK: access rules, admin gate, sending. Every behaviour.
│   └── mcp/tools.py        # The five tools: one SDK call each.
├── docs/channels/          # One setup guide per documented channel type.
└── tests/
    ├── unit/sdk/           # SDK tests (the coverage audit reads these).
    ├── unit/test_http_stack.py   # The real ASGI app against mcp-app's test issuer.
    └── framework/          # mcp-app's conformance suite pointed at this App.
```

## Architecture

Three layers. **All behaviour is in `alerts/sdk/`.** `alerts/mcp/tools.py` is
one SDK call per tool plus turning an `AlertsError` into `{"error": ...}`.
There is no CLI of its own: `alerts-mcp` and `alerts-admin` come from the
`App` object (mcp-app). If you find yourself writing logic in a tool, move it
to the SDK.

The SDK is a stateless class used as a namespace (`sdk = AlertsSDK`; tools
call `sdk.method()`), so the coverage audit in `tests/framework/` can match
each tool to SDK tests by method name.

Identity comes from mcp-app's `current_user`: the HTTP middleware sets it per
request, the stdio command sets it from `--user`. The app declares no profile
model: a user record carries admission state only, and the app's own
per-user data (grants) goes through `mcp_app.get_store()`.

## Rules to preserve

1. **Credentials live in the channel definitions and nowhere else.** The
   `ALERTS_CHANNELS` variable or the channels file is the only place an
   Apprise URL exists. `channels.py` returns channel names and Apprise
   `service_name`s; nothing returns, logs, or stores a URL, not even a
   redacted one, and invalid lines are reported by channel name and line
   number. Keep it that way in every new field of every response: an agent's
   tool result lands in a transcript.
2. **No credential ever passes through model context.** There is no tool that
   registers a channel or takes a URL: an operator writes the line, a
   deployment's secret store carries it. Granting is by name. Do not add a
   tool argument that could carry a destination URL, even "for convenience".
3. **Administrator-only tools are enforced in the SDK, at call time.**
   `AlertsSDK.require_admin` accepts the stdio operator (`mcp_app.is_stdio()`)
   or an `ADMIN_EMAILS` entry (`mcp_app.auth.is_admin`). mcp-app hides and
   blocks only its own framework admin tools from non-administrators; it has
   no marker yet for an app's admin tools, so `grant_channel` and
   `revoke_channel` are listed to every user and refuse at call time. The
   check in the SDK is the real protection and must stay in every admin
   method; hiding the tools is a framework feature to adopt when it exists.
4. **Access is grants over HTTP, everything over stdio.** `available()` is the
   one place that decides what a caller may send to: over stdio the local
   user is the operator and has every configured channel; over HTTP a user
   has the channels granted to them. The default is the user's granted
   default, or the only available channel when there is exactly one. Both
   `list_channels` and `notify` go through it.
5. **Sending reports per destination and never raises past the SDK boundary
   for a delivery failure.** A channel can have several destinations; each is
   sent with a timeout (`SEND_TIMEOUT_SECONDS`) and reported as
   `{"service", "ok", "error"?}`; `sent` is true only when all succeeded. A
   plugin exception is reported by type, never with the URL.
6. **`urgency` maps to Apprise's notification type** (`URGENCIES`: low to
   info, normal to warning, high to failure). Channels colour or tag by it.
   Don't add urgency values that no channel can express.
7. **The link is plain text.** `compose()` appends the conversation URL on its
   own line, and messages go out as `NotifyFormat.TEXT`. Phones auto-link
   URLs; markup renders differently per service and is not worth it.
8. **Channel types are documented in one table.** `channels.CHANNEL_TYPES`
   drives `list_channel_types`; each entry names the Apprise service (for its
   docs link, read from Apprise at call time), the URL form an operator
   writes, and the notes that matter before choosing it. Adding a type means
   an entry there and, for the common ones, a guide in `docs/channels/` linked
   from the README. Leave desktop-only Apprise plugins out. Email entries say
   port 587 or 465: cloud platforms block outbound 25.
9. **mcp-app is pinned to a released tag** in `pyproject.toml`. Upgrading it
   is its own commit: change the pin, reinstall, run `pytest`, then commit.

## Tests

```bash
make test        # creates .venv with an editable install on first run, then pytest
```

`pytest` runs three suites, no network and no credentials:

- `tests/unit/sdk/`: the SDK against a temp store. A test-only Apprise plugin
  (`capture://`, registered in `conftest.py` with Apprise's `@notify`
  decorator) records what would be sent, so the real Apprise pipeline runs
  end to end without a network; `failing://` always refuses.
- `tests/unit/test_http_stack.py`: the real ASGI stack through httpx's ASGI
  transport against `mcp_app.testing`'s stand-in issuer: an administrator
  grants through the MCP layer, the user sends, a non-administrator is
  refused.
- `tests/framework/`: mcp-app's conformance suite (auth enforcement, admin
  CLI local mode, wiring, health, and the audit that every SDK method a tool
  calls is named in a test under `tests/unit/sdk/`). `conftest.py` is the
  only app-specific file.

Tests are sociable: real code, real files in temp directories, the one stub
being the notification plugin that stands in for the network. Fixtures never
contain a real-looking webhook, topic or address.

**Live checks run the installed CLI.** Before trusting a stdio smoke test or
an `alerts-admin` run, confirm the install is editable: `pipx list | grep -A5
alerts` must show `(editable)`; `--version` does not reveal a stale snapshot.
Fix with `pipx install -e . --force`.

A stdio smoke test with no MCP client: point a channel at a local HTTP
listener with Apprise's `json://127.0.0.1:<port>/` scheme, start
`alerts-mcp stdio --user local`, and drive `tools/call` with the MCP Python
client. `make test` already covers the transport in process.

## Adding a tool

Add an async function to `alerts/mcp/tools.py` whose body is one
`sdk.<method>()` call inside the `AlertsError` guard; add the method to
`AlertsSDK`; add a test in `tests/unit/sdk/` that names the method. Type
hints become the schema and the docstring the description that agents and
`alerts-admin tools show` display, so write it for an agent deciding whether
and how to call the tool, and keep rules 1 and 2 above. A tool that changes
sharing of a channel is administrator-only: call `cls.require_admin()` first.

## Deployment configuration and environment variables

The repo describes what the server needs from any environment and nothing
about where it runs: the Dockerfile and the README's runtime contract are
the whole deployment story. No deployment tool's configuration file, and no
value that identifies one deployment (issuer, administrators, domain,
project), is ever committed here. Those live in the operator's own
deployment records.

The README's [Environment variables](README.md#environment-variables)
section is the contract for configuration: a quick-look table (variable,
transport, required, type, default when unset, secret) and a reference entry
per variable (format and accepted values, an example, what happens when it
is missing or wrong). A change that reads a new variable, or changes how one
is parsed or defaulted, updates both in the same commit.
`tests/unit/test_env_docs.py` fails when a variable the code reads is
missing from the table.

## Releases

The version comes from git tags; there is no number to edit. `setuptools-scm`
derives it at build time: a commit tagged `vX.Y.Z` builds as `X.Y.Z`, a later
commit as a dev version. Builds from a `git archive` snapshot (the container
build) read it from `.git_archival.txt`, which `.gitattributes` marks
`export-subst`; keep both files.

| Change | Bump |
|---|---|
| Fix | patch |
| Feature, or a breaking change while on 0.x | minor (say "breaking" in the tag message) |
| New major | only with the maintainer's explicit approval |

Release: merge the reviewed change to `main`, tag that commit
(`git tag -a vX.Y.Z -m vX.Y.Z` and push the tag), deploy that tag through
the operator's deployment pipeline (never a local build), then verify with
`alerts-admin probe` and a `notify` from a real MCP client. Update any install pin that names a
version only after the tag exists on GitHub.

## Pre-commit

Commits are scanned for credentials and personal data before they land.
Don't bypass the hook; surface a false positive instead.
