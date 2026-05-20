# Trello Agent — Tools & Configuration

## Environment variables

```bash
TRELLO_API_KEY    # From https://trello.com/power-ups/admin
TRELLO_TOKEN      # OAuth token from Trello authorization
TRELLO_BOARD_ID   # Board ID from the board URL (trello.com/b/<BOARD_ID>/...)
```

## Trello API

Base URL: `https://api.trello.com/1`

Key endpoints used by `trello-sync.py`:
- `GET /boards/{id}/lists` — fetch all lists on the board
- `GET /boards/{id}/cards` — fetch all cards on the board
- `POST /cards` — create a new card
- `PUT /cards/{id}` — update card (column move = update listId)
- `POST /cards/{id}/actions/comments` — add a comment
- `GET /cards/{id}/actions` — fetch card activity

## Sync script

`scripts/trello-sync.py` — Python 3, standard library only (no pip packages required beyond `requests` if used)

Usage:
```bash
# Sync Trello → database
python3 trello-sync.py

# Initialise database
python3 trello-sync.py --init

# Generate daily report
python3 trello-sync.py --report

# Dry run (read-only)
python3 trello-sync.py --dry-run
```

## Database

SQLite at: `~/central-tasks/tasks.db`

Schema:
```sql
CREATE TABLE tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  trello_card_id TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT NOT NULL,  -- 'todo' | 'in_progress' | 'blocked' | 'done'
  column_name TEXT NOT NULL,
  assigned_agent TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME,
  blocked_reason TEXT,
  completion_summary TEXT
);
```

## Error handling

- API errors → log to stderr, exit with code 1
- Network errors → retry up to 3 times with 5s backoff
- Auth errors → immediately fail and report (do not retry silently)
- DB errors → fail immediately (data integrity over availability)