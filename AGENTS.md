# Trello Task Protocol — Agent Rules

These rules apply to **every agent** in the system, regardless of harness (OpenClaw, Hermes, or other).

## Core principle

Every task created by any agent must appear as a Trello card. No exceptions.

## Board columns (exact names, no variants)

- `To-Do`
- `In Progress`
- `Blocked`
- `Done`

## Task lifecycle

### New tasks → To-Do
1. Agent creates a Trello card in the **To-Do** column
2. Immediately logs it in the central database (`~/central-tasks/tasks.db`)
3. Decides best assigned agent (or self-assigns)
4. Moves card to **In Progress**

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
- **Central orchestrator (Milton/main)**: monitors To-Do, assigns tasks, ensures sync between Trello and database

## Permanent rules

- Every task must be a Trello card
- All tasks start in To-Do
- Only these four columns are used — no others
- Blocked cards must have the exact blocked comment format before moving
- Done cards must have a completion summary before moving
- Trello and `tasks.db` must always be in sync