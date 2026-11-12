# ntfy channel

[ntfy](https://ntfy.sh) is a publish/subscribe push service with its own
phone app (Android and iOS) and no account requirement. You pick a **topic**;
the phone app subscribes to it; anything published to the topic arrives as a
notification. The alert's `link` is a plain URL in the body, which the app
renders tappable.

## Pick a topic

On the public server (`ntfy.sh`) the topic name is the only thing protecting
the channel: anyone who knows it can publish to it and read it. Choose a
long random name, and treat it as a secret.

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

A self-hosted ntfy server, or a reserved topic on ntfy.sh with a paid plan,
adds a user and password; both go in the URL.

## Subscribe the phone

Install the ntfy app, **Subscribe to topic**, enter the topic (and the server
if self-hosted). Allow notifications for the app. Done.

## The channel line

```
phone = ntfys://ntfy.sh/<topic>
phone = ntfys://<user>:<password>@ntfy.example.com/<topic>
```

`ntfys://` is the TLS form; `ntfy://` is plain HTTP for a server on a private
network. Options go on the URL: `?priority=high` raises the notification's
priority on the phone for every alert through that line, `?click=<url>` sets
a tap target (the alert's own `link` is already in the body, so this is
rarely needed). Full option list in Apprise's ntfy documentation:
<https://appriseit.com/services/ntfy/>.

## What an alert looks like

The `title` is the notification heading, the `message` the body with the
`link` on its own line. `urgency` has no visible effect on ntfy: Apprise
sends ntfy no tag or priority per message, so the phone's notification
priority comes from the line's `?priority=` option (and an emoji from
`?tags=`). To tell urgencies apart on ntfy, define two channels on two
lines with different options and let the agent pick the channel.

ntfy is one-way for this server: the app can show action buttons and even
reply through a separate publish, but nothing typed there reaches the agent.
Tap the link to answer in the conversation.
