# Slack webhook channel

A Slack app's **Incoming Webhook**, posting into the app's own direct-message
conversation with you. Because the message comes from the app rather than from
you, Slack delivers it like a message from someone else: the phone buzzes,
even though you wrote nothing. A webhook is one-way; a reply typed under the
message stays in Slack, which is why every alert carries a link back to the
conversation.

## Why not post as yourself

Slack never pushes a notification for your own messages, including a message
to yourself. Any integration that posts *as you* (a user token, a Slack
connector signed in as you) is silent on the phone. The webhook of an app you
create posts as the app.

## Create the app

In [api.slack.com/apps](https://api.slack.com/apps), **Create New App**, from
scratch or from a manifest, in your workspace. Name it for what it is (for
example "Agent Alerts"); the name is what the phone shows.

If you use a manifest, give the app a bot user with the `chat:write` scope.
Do not list `incoming-webhook` as a bot scope: the manifest validator rejects
it. Incoming Webhooks are turned on in the app's settings after creation:

1. **Incoming Webhooks** in the app's left menu, switch it on.
2. **Add New Webhook to Workspace**.
3. For the destination, choose the **app's own DM** (its name under "Apps" or
   "Direct messages"), not your own direct-message-to-self conversation.
   Posting into your self-DM is still a message from you and stays silent.
4. Copy the webhook URL. It looks like
   `https://hooks.slack.com/services/T.../B.../...`.

Install (or reinstall) the app to the workspace when prompted.

## The channel line

Paste the webhook URL as is; Apprise recognises it. In
`~/.config/alerts/channels` (local) or the `ALERTS_CHANNELS` secret
(deployment):

```
phone = https://hooks.slack.com/services/T.../B.../...
```

The URL is the credential. Anyone holding it can post into that DM. Keep it
in the channel definitions only; if it leaks, delete the webhook on the app's
Incoming Webhooks page and add a new one, then replace the line.

## Make it buzz

- Slack **suppresses mobile push while you are active on the desktop app.** In
  Slack on the phone: Notifications, then turn on sending notifications to
  mobile even when active on desktop (the wording varies by version).
- Check the app's DM is not muted and your phone allows Slack notifications.

## What an alert looks like

The alert's `title` is the message heading, the `message` follows, and the
`link` is appended as a plain URL on its own line; Slack renders it as a
tappable link. `urgency` colours the message: blue for `low`, orange for
`normal`, red for `high`.

Apprise's Slack documentation, including the `slack://` form that takes the
three webhook tokens separately: <https://appriseit.com/services/slack/>.
