# Trello Agent — Heartbeat

## Sync trigger (every ~5 minutes)

Run `trello-sync.py` to sync Trello board state with the central database:

```bash
python3 ~/central-tasks/scripts/trello-sync.py
```

If there are errors, report them to the orchestrator agent.

## Daily evening report

Generate and deliver the daily report at the configured time (default 7 PM local):

```bash
python3 ~/central-tasks/scripts/trello-sync.py --report
```

Deliver via the configured channel (Telegram, Discord, email, etc.).

## Check

- Is the board accessible?
- Did any cards move since last run?
- Any blocked cards need attention?
- Any cards in the wrong column?