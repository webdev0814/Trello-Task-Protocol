# Trello Task Protocol — Agent Rules

These rules apply to **every agent** in the system, regardless of harness (OpenClaw, Hermes, or other).

## Core principle

Every task created by any agent must appear as a Trello card. No exceptions.

## Board columns (exact names, no variants)

- `To-Do`
- `In Progress`
- `Blocked`
- `Done`
- `Jason` is a human-only label. Cards with that label are ignored by agents and dispatcher automation.

## Task lifecycle

### New tasks → To-Do
1. Agent creates a Trello card in the **To-Do** column
2. Applies the assigned agent label
3. Immediately logs it in the central database (`~/central-tasks/tasks.db`)
4. Adds the exact comment `Starting work`
5. Moves card to **In Progress**
6. Begins work immediately

### In Progress
- Agent is actively working on the task
- Add progress comments to the card as needed
- If blocked, move to Blocked and add the blocked comment (see below)

### Blocked
When a task cannot continue, move to **Blocked** and add this exact comment format:

```
🔴 BLOCKED
Reason: [clear explanation of what is blocking the task]
Needed to Unblock: [specific thing required — e.g., "human approval on X", "waiting for info Y"]
Who needs to act: [human or specific agent name]
Estimated resolution: [e.g., "once human replies", "2 hours after receiving Z"]
Workaround (if any): [temporary solution the agent suggests]
```

### Done
When task is fully complete:
1. Add a short completion summary comment to the card
2. Move the card to **Done**
3. Update the central database

## Agent responsibilities

- **Trello Agent**: creates cards, moves cards, updates comments as instructed by other agents or humans
- **All agents**: must use Trello for all tasks; no task tracking outside Trello
- **Dispatcher**: monitors labeled To-Do/In Progress cards every 1-2 minutes, notifies assigned agents, claims new To-Do cards, and escalates stale unclaimed cards
- **Central orchestrator (Milton/main)**: receives watchdog escalations and owns routing until transfer to Michael is explicitly approved

## Permanent rules

- Every task must be a Trello card
- All tasks start in To-Do
- Starting work requires the exact comment `Starting work`, then moving to In Progress
- Only these four columns are used — no others
- Blocked cards must have the exact blocked comment format before moving
- Done cards must have a completion summary before moving
- Trello and `tasks.db` must always be in sync
- Cards labeled `Jason` are reserved for the human and must not be claimed, moved, or dispatched by agents

## Hard Rule: Agents Must Label Their Own Cards

When creating a Trello card, you MUST immediately apply your agent label to it
(e.g., `Kevin 🧮`, `Michael 🎤`, `Dwight 🏃`, `Pam 🐻`). Unlabeled cards in
To-Do will NOT be dispatched automatically.
