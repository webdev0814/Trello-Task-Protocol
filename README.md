# Trello Task Protocol

This repository contains a lightweight Trello toolkit for a prompt-contract workflow:

- Read cards from selected lists.
- Post initial prompt-contract comments when a card is missing one.
- Build a local inbox of cards that need review after new human comments.
- Surface stale `To-Do` and `In Progress` cards for proactive follow-up on a cooldown.
- Refresh a webhook-first active inbox, with polling only as scheduled reconciliation.
- Move cards between `To-Do`, `In Progress`, `Blocked`, and `Done`.
- Receive Trello webhooks, verify signatures, and queue follow-up work.

The toolkit supports both polling and a webhook-ready event layer. Deployment details stay in local environment files and are not committed.

## Files

- `.env.local`: local Trello credentials and board settings. This file is git-ignored.
- `src/commands/snapshot.mjs`: fetches the current board state and writes `data/board-snapshot.json`.
- `src/commands/bootstrap-contracts.mjs`: posts prompt-contract comments to cards that do not already have one.
- `src/commands/refresh-inbox.mjs`: refreshes `data/trello-active-inbox.json` from webhook activity first, and only falls back to poll when reconciliation is due.
- `src/commands/poll-once.mjs`: builds `data/trello-inbox.json` with cards that need review.
- `src/commands/post-comment.mjs`: posts a comment to a Trello card.
- `src/commands/move-card.mjs`: moves a card to a named list.
- `src/commands/webhook-server.mjs`: runs the local Trello webhook receiver.
- `src/commands/register-webhook.mjs`: registers a board webhook once you have a public callback URL.
- `src/commands/drain-webhook-queue.mjs`: turns queued webhook events into a card inbox.
- `src/commands/sync-oracle-webhook-inbox.mjs`: optionally drains a remote webhook queue over SSH and copies the resulting inbox back to the local workspace.

## Required setup

1. Create a `.env.local` file from `.env.example`.
2. Fill in your Trello API key, API secret, token, and board details locally.
3. When you are ready for webhook ingress, replace `TRELLO_WEBHOOK_CALLBACK_URL` with a public HTTPS URL that points to your webhook server.

Authorization URL template:

`https://trello.com/1/authorize?expiration=never&scope=read,write&response_type=token&name=Codex%20Trello%20Agent&key=<your key>`

Never commit `.env.local` or any real credentials.

## Commands

Run one board snapshot:

```powershell
npm run trello:snapshot
```

Post missing prompt contracts to existing cards in the target lists:

```powershell
npm run trello:contracts
```

Build the local inbox of cards that need follow-up after new human activity:

```powershell
npm run trello:poll
```

By default, `trello:poll` also re-queues stale `To-Do` and `In Progress` cards once every 24 hours so active cards do not disappear from the workflow after the initial contract exchange.

Refresh the active inbox using webhook activity first, with polling only as a twice-daily reconciliation backstop:

```powershell
npm run trello:refresh
```

Run the local webhook receiver:

```powershell
npm run trello:webhook:serve
```

List currently registered Trello webhooks for this token:

```powershell
npm run trello:webhook:list
```

Register a board webhook after you have a public callback URL:

```powershell
npm run trello:webhook:register -- --callback-url "https://your-public-host.example/trello/webhook"
```

Drain queued webhook events into `data/trello-webhook-inbox.json`:

```powershell
npm run trello:webhook:drain
```

If webhook ingress is hosted remotely, sync the remote inbox down to this workspace:

```powershell
npm run trello:webhook:sync-oracle
```

Post a comment from stdin:

```powershell
'Agent reply text' | npm run trello:comment -- --card <card-id>
```

Move a card by target list name:

```powershell
npm run trello:move -- --card <card-id> --list "In Progress"
```

## Recommended architecture

1. Run the webhook receiver on a public endpoint.
2. Register one board webhook against that endpoint.
3. Let the receiver append validated events to the remote webhook queue.
4. Run `npm run trello:refresh` so webhook activity is processed first.
5. Let `npm run trello:refresh` invoke `npm run trello:poll` only when the reconciliation interval is due.

This split keeps Trello API access inside small local commands and leaves language reasoning to the agent layer.

## Reconciliation cadence

`npm run trello:refresh` treats webhook-triggered card changes as the normal source of work. It only runs the polling workflow when no webhook work is available and the reconciliation interval has elapsed.

- Default reconciliation interval: 12 hours
- Override with `TRELLO_RECONCILIATION_POLL_INTERVAL_HOURS`

## Active-card follow-up cadence

These intervals control how often unchanged active cards can reappear in the inbox as proactive `needs_review` items:

- `TRELLO_TODO_REVIEW_INTERVAL_HOURS` default: 24
- `TRELLO_IN_PROGRESS_REVIEW_INTERVAL_HOURS` default: 24

## Public URL note

Trello validates webhook callback URLs by making an HTTP `HEAD` request and expecting a `200` response. Localhost URLs will not work for registration. You can still run the server locally now and later put it behind a public HTTPS endpoint or tunnel, then register the webhook.
