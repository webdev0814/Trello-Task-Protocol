# Trello Task Protocol — Agent Skill

A harness-agnostic task management protocol for AI agent systems. Ensures every task created by any agent is tracked in Trello with strict column rules, synchronised to a local SQLite database, and enforced across all agents.

## What it does

- Every task created by any agent → Trello card in **To-Do** column
- Agents move cards through: **To-Do → In Progress → Blocked → Done**
- Blocked cards get a structured comment: reason, unblock requirements, who needs to act, estimated resolution, workaround
- Done cards get a short completion summary before moving
- A sync script keeps Trello and a local `tasks.db` (SQLite) perfectly synchronised
- Daily evening report generated automatically

## Architecture

```
Agent (any harness)
  → creates task → Trello card (To-Do column)
  → moves card → In Progress / Blocked / Done
  → sync script → central tasks.db (SQLite)
  → daily report cron → Telegram / channel
```

## Four columns only

- **To-Do** — new tasks only; agent reviews, logs to DB, assigns, moves to In Progress
- **In Progress** — agent started work; progress comments added as needed
- **Blocked** — work cannot continue; structured comment required (see below)
- **Done** — task complete; short summary comment required before moving

## Blocked card format

When a card is blocked, the agent must add this exact format as a card comment:

```
🔴 BLOCKED
Reason: [clear explanation of what is blocking the task]
Needed to Unblock: [specific thing required — e.g., "Jason's approval", "waiting for info Y"]
Who needs to act: [person / agent responsible]
Estimated resolution: [e.g., "once Jason replies", "2 hours after receiving Z"]
Workaround (if any): [temporary solution the agent suggests]
```

## Installation

### 1. Copy the skill files to your agent workspace

```bash
# For OpenClaw agents, copy into the agent's workspace directory
cp -r SKILL.md AGENTS.md IDENTITY.md TOOLS.md SOUL.md HEARTBEAT.md USER.md ~/openclaw/agents/<agent-name>/

# For Hermes/Paperclip agents, copy into the agent's workspace
cp -r SKILL.md AGENTS.md IDENTITY.md TOOLS.md SOUL.md HEARTBEAT.md USER.md ~/hermes/agents/<agent-id>/
```

### 2. Configure Trello credentials

Set these environment variables (or in your agent's secure config):

```bash
export TRELLO_API_KEY="your_trello_api_key"
export TRELLO_TOKEN="your_trello_oauth_token"
export TRELLO_BOARD_ID="your_board_id"  # Found in the board URL: trello.com/b/<BOARD_ID>/...
```

### 3. Install the sync script

```bash
cp scripts/trello-sync.py /path/to/central-tasks/scripts/trello-sync.py
chmod +x /path/to/central-tasks/scripts/trello-sync.py
```

### 4. Initialise the database

```bash
python3 /path/to/central-tasks/scripts/trello-sync.py --init
```

### 5. Schedule the sync

Add a cron job (example every 5 minutes):

```bash
# OpenClaw cron example
openclaw cron add --name "trello-sync" \
  --schedule "every 5m" \
  --payload "Run /path/to/central-tasks/scripts/trello-sync.py and report only on errors" \
  --session isolated
```

Or via cron expression (every 5 min):

```
*/5 * * * *
```

## Central database

The sync script uses SQLite at `~/central-tasks/tasks.db` with this schema:

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

## Daily report

Generate a daily report (example cron at 7 PM):

```
0 19 * * * /path/to/central-tasks/scripts/trello-sync.py --report
```

Report includes:
- All tasks created today
- Current status of every active task (with column name)
- Any Blocked tasks with their full blocked comment

## SKILL.md contents

- `SKILL.md` — this file; protocol overview + install
- `AGENTS.md` — rules for all agents (task creation, column rules, blocked/done formats)
- `IDENTITY.md` — agent persona (e.g., "Trello Agent")
- `TOOLS.md` — Trello API notes, sync script path, environment variables
- `SOUL.md` — core behavioral guidelines
- `HEARTBEAT.md` — periodic sync checklist (if applicable)
- `USER.md` — user-specific context (board URL, reporting channel, etc.)
- `scripts/trello-sync.py` — the sync engine (Python 3, no external dependencies beyond `requests`)

## Supported agent harnesses

Tested / compatible with:
- **OpenClaw** — native plugin, cron scheduling, agent workspaces
- **Hermes / Paperclip** — via SSH/agent-run, same sync script
- **Any agent** that can run Python and make API calls

## Safety notes

- Never commit `TRELLO_API_KEY`, `TRELLO_TOKEN`, or any secrets to the repo
- The sync script is read-mostly; it only creates/moves comments on Trello
- The DB file (`tasks.db`) is local only; no network exposure
- Review the blocked comment format before deploying to ensure it matches your workflow

## License

MIT — free to use, modify, and distribute in any AI agent harness.