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
- Cards with no label are ignored by dispatcher automation until someone labels them.

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
- Add one substantive progress comment only when there is real progress, a concrete blocker, or completion
- If the card is labeled `Jason`, do not comment, move, or dispatch it
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
- **Dispatcher**: monitors labeled To-Do/In Progress/Done cards every 1-2 minutes, notifies assigned agents only on new meaningful activity or first assignment, leaves new To-Do cards unclaimed until the agent claims them in Trello, escalates stale unclaimed cards, and auto-blocks stale In Progress cards only after a verifiable agent claim and no follow-up activity after notification
- **Central orchestrator (Milton/main)**: receives watchdog escalations and owns routing until transfer to Michael is explicitly approved

## Permanent rules

- Every task must be a Trello card
- All tasks start in To-Do
- Starting work requires the exact comment `Starting work`, then moving to In Progress
- Only these four columns are used — no others
- Blocked cards must have the exact blocked comment format before moving
- Done cards must have a completion summary before moving
- Trello and `tasks.db` must always be in sync
- Cards labeled `Jason` are reserved for the human and must not be claimed, moved, commented on, or dispatched by agents

## Hard Rule: Agents Must Label Their Own Cards

When creating a Trello card, you MUST immediately apply your agent label to it
(e.g., `Kevin 🧮`, `Michael 🎤`, `Dwight 🏃`, `Pam 🐻`). Unlabeled cards in
To-Do are ignored by dispatcher automation until they are explicitly labeled.

## Mandatory Telegram + DoD Rule

Applies to all agents: Pam, Michael, Dwight, and Kevin.

When a user posts a task in Telegram:

1. Immediately create a Trello card in `To-Do`.
2. Set the card title to a one-line task summary.
3. Set the card description to the full task plus:

```
Definition of Done:
- [measurable #1]
- [measurable #2]
- Verified by [who/how]
```

4. Add your own agent label: `Pam`, `Michael`, `Dwight`, or `Kevin`.
5. Post an initial plan comment.
6. Move the card to `In Progress` if unblocked.

## Proactive Work Rule

Poll your `In Progress` cards every heartbeat. Work until blocked or done:

- If blocked, use the exact 🔴 BLOCKED format.
- If Definition of Done is met, add a completion summary and move the card to `Done`.
- If the next step depends on Jason, another person, credentials, external systems, or a broken agent runtime, move the card to `Blocked`; do not park it in `In Progress`.
- If the card is labeled `Jason`, ignore it completely.

## Closed-Loop Enforcement Rule

Dispatcher notifications are not success. A task is only considered handled when Trello shows the card left `In Progress` for an outcome state: `Blocked` or `Done`.

If a card remains in `In Progress` after an agent notification beyond the configured action SLA, the dispatcher must add the required blocked comment, move the card to `Blocked`, and escalate to Milton for triage.

## Comment Rule

On any comment to your card, whether received through the `commentCard` webhook or a dispatcher ping, resume work immediately until blocked or done.

## Dwight QA Gate

For non-trivial changes to this Trello automation, dispatcher, sync logic, cron behavior, or GitHub-pushed code, Dwight must QA the change before it is considered complete.

- QA the live/deployed behavior when possible, not only the diff.
- Return PASS/FAIL, evidence checked, and any required fix.
- If QA finds a second source of the same spam or routing problem, fix that source too before closing.

## Standing QA Rule

Every non-trivial update to this protocol, dispatcher, or Trello automation must be QA'd by Dwight before it is pushed or declared done.
