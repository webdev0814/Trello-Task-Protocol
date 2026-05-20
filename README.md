# Trello Task Protocol — Agent Skill

**A harness-agnostic task management protocol for AI agent systems.**

Every task created by any agent is tracked in Trello with strict column rules, synchronised to a local SQLite database, and enforced across all agents. No task gets lost. No agent works on something untracked.

---

## The problem

AI agents create lots of tasks — research, coding, ops, follow-ups. Without a strict system, tasks get lost, agents step on each other, and there's no single source of truth for what's happening.

Most agent frameworks don't enforce task management. This protocol does.

---

## What it solves

- **Every agent uses the same board** — no task gets created outside Trello
- **Four-column discipline** — To-Do → In Progress → Blocked → Done. No exceptions.
- **Structured blocked/done comments** — every blocked task has a reason, unblock requirement, who needs to act, estimated resolution, and workaround
- **Central database sync** — Trello and a local SQLite DB stay perfectly in sync
- **Automated daily reports** — every evening, a report goes out showing new tasks, active tasks, and blocked tasks
- **Harness-agnostic** — works with OpenClaw, Hermes/Paperclip, or any AI agent that can run Python and call APIs

---

## Core concepts

### The board

Only four columns are used. Nothing else.

| Column | Meaning |
|--------|---------|
| **To-Do** | New tasks. Created here. Agent reviews, assigns, moves to In Progress. |
| **In Progress** | Agent is actively working on it. |
| **Blocked** | Work cannot continue. Structured comment required (see below). |
| **Done** | Task complete. Completion summary required before moving. |

### Task lifecycle

```
Agent creates task → Card appears in To-Do
  → Central orchestrator reviews, logs to DB, assigns, moves to In Progress
  → Agent works, adds progress comments as needed
  → If blocked → move to Blocked, add structured comment
  → When done → add completion summary, move to Done
  → Sync script keeps Trello and tasks.db aligned
```

### Blocked card format

When a card is blocked, the agent must add this exact format as a card comment:

```
🔴 BLOCKED
Reason: [clear explanation of what is blocking the task]
Needed to Unblock: [specific thing required — e.g., "human approval on X", "waiting for info Y"]
Who needs to act: [human or specific agent name]
Estimated resolution: [e.g., "once human replies", "2 hours after receiving Z"]
Workaround (if any): [temporary solution the agent suggests]
```

### Completion summary

Before moving a card to Done, add a short comment describing what was accomplished.

---

## Quick start (5 minutes)

### 1. Get Trello credentials

```bash
# From https://trello.com/power-ups/admin
export TRELLO_API_KEY="your_api_key"
export TRELLO_TOKEN="your_oauth_token"

# Board ID from the URL: trello.com/b/<BOARD_ID>/...
export TRELLO_BOARD_ID="your_board_id"
```

### 2. Copy files to your agent workspace

```bash
# For OpenClaw agents
cp -r SKILL.md AGENTS.md IDENTITY.md TOOLS.md SOUL.md HEARTBEAT.md USER.md \
  ~/.openclaw/agents/<agent-name>/

# For Hermes/Paperclip agents
cp -r SKILL.md AGENTS.md IDENTITY.md TOOLS.md SOUL.md HEARTBEAT.md USER.md \
  ~/hermes/agents/<agent-id>/
```

### 3. Install the sync script

```bash
mkdir -p ~/central-tasks/scripts
cp scripts/trello-sync.py ~/central-tasks/scripts/
chmod +x ~/central-tasks/scripts/trello-sync.py
```

### 4. Initialise the database

```bash
python3 ~/central-tasks/scripts/trello-sync.py --init
```

### 5. Schedule the sync

Add to your agent's heartbeat (every ~5 minutes):

```bash
python3 ~/central-tasks/scripts/trello-sync.py
```

Add a daily report cron (example 7 PM):

```bash
# Run daily report
0 19 * * * python3 ~/central-tasks/scripts/trello-sync.py --report
```

---

## The sync script

`scripts/trello-sync.py` — Python 3, no pip dependencies required (uses the standard library + `requests`).

### Usage

```bash
# Sync Trello ↔ database (every 5 min via heartbeat)
python3 trello-sync.py

# Initialise the database (first time only)
python3 trello-sync.py --init

# Generate daily report
python3 trello-sync.py --report

# Dry run (read-only check)
python3 trello-sync.py --dry-run
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `TRELLO_API_KEY` | From trello.com/power-ups/admin |
| `TRELLO_TOKEN` | OAuth token from Trello |
| `TRELLO_BOARD_ID` | Found in board URL: `trello.com/b/<BOARD_ID>/...` |
| `TASKS_DB` | Optional. Path to SQLite DB. Default: `~/central-tasks/tasks.db` |

---

## Database schema

SQLite at `~/central-tasks/tasks.db`:

```sql
CREATE TABLE tasks (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  trello_card_id    TEXT UNIQUE NOT NULL,
  title             TEXT NOT NULL,
  description       TEXT,
  status            TEXT NOT NULL,  -- 'todo' | 'in_progress' | 'blocked' | 'done'
  column_name       TEXT NOT NULL,  -- 'To-Do' | 'In Progress' | 'Blocked' | 'Done'
  assigned_agent    TEXT,
  created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
  completed_at      DATETIME,
  blocked_reason    TEXT,
  completion_summary TEXT
);
```

---

## Supported agent harnesses

Tested and compatible with:
- **OpenClaw** — native cron scheduling, agent workspaces, plugin system
- **Hermes / Paperclip** — SSH-based agent runs, Python sync script
- **Any agent** that can run Python 3 and make HTTP API calls

The protocol is harness-agnostic. The agent files (SKILL.md, AGENTS.md, etc.) are written in plain Markdown and work in any agent framework that reads workspace instructions.

---

## File overview

| File | Purpose |
|------|---------|
| `SKILL.md` | This file. Protocol overview + quick start. |
| `AGENTS.md` | Rules for every agent — column names, task lifecycle, blocked/done formats. |
| `IDENTITY.md` | Agent persona template (e.g., "Trello Agent"). Fill in per deployment. |
| `TOOLS.md` | Trello API endpoints, sync script usage, environment variables. |
| `SOUL.md` | Core behavioral rules — no fluff, no shortcuts. |
| `HEARTBEAT.md` | Periodic sync checklist (every ~5 min + daily report). |
| `USER.md` | User-specific config: board URL, reporting channel, schedule. |
| `scripts/trello-sync.py` | The sync engine. Python 3, SQLite + Trello API. |
| `LICENSE` | MIT — free to use, modify, distribute. |

---

## Example daily report output

```
📋 Daily Trello Report

✅ Created today: 3
  • Fix auth bug in login flow → To-Do
  • Research AWS Activate credits → In Progress
  • Update agent HEARTBEAT.md files → Done

📌 Active tasks (5):
  [In Progress] Research Florida VBOC programs
    Assigned: Milton
  [In Progress] Write trello-sync.py daily report
    Assigned: Trello Agent

🔴 Blocked (1):
  • Apply for SBA VOSB certification
    🔴 BLOCKED
    Reason: Need EIN document from Jason
    Needed to Unblock: EIN certificate PDF
    Who needs to act: Jason
    Estimated resolution: within 24h
    Workaround: Use business name for now

🏁 Done today: 2
  • Set up Trello Agent workspace
    Completed: all files created, sync script tested
  • Enforce Trello protocol across all agents
    Completed: propagated to Pam, Dwight, Kevin, Michael
```

---

## Safety notes

- **Never commit secrets** — `TRELLO_API_KEY`, `TRELLO_TOKEN`, and `TRELLO_BOARD_ID` must never appear in the repo. Use environment variables or a secrets manager.
- **The sync script is read-mostly** — it creates cards, moves cards, and adds comments. It does not delete data.
- **DB is local only** — `tasks.db` is stored on the local filesystem. It is not exposed over the network.
- **Auth errors fail immediately** — the script does not retry silently on auth failures. This is intentional to prevent data drift from credential issues.

---

## Contributing

Contributions welcome. Please keep the protocol harness-agnostic — no OpenClaw-specific or Hermes-specific references in the core docs. Platform-specific notes belong in separate files or the documentation site.

---

## License

MIT — see [LICENSE](LICENSE).