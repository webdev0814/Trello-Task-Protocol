## Rule: Agents Must Label Their Own Cards

When any agent creates a new Trello card, they MUST:
1. Immediately apply their own agent label (e.g., `Kevin 🧮`, `Michael 🎤`, `Dwight 🏃`, `Pam 🐻`, `Milton 🦞`)
2. Place the card in `To-Do` by default
3. Add the initial comment "Starting work" and move it to `In Progress`

This is enforced because:
- The Trello dispatcher routes cards by label only
- Unlabeled cards are ignored by the dispatcher until they receive a label
- The dispatcher's `choose_agent()` function no longer falls back to keyword matching; label priority is the only routing path

### Enforcement in the dispatcher

The dispatcher at `scripts/trello-dispatcher.py` will:
- Skip `Jason`-labeled cards silently and leave no comments or moves on them
- Skip unlabeled cards silently and leave no comments or moves on them
- If a `Jason`-labeled card also detects an agent name/keyword in the title, ignore it without side effects
- Notify agents about labeled `To-Do` cards without auto-claiming them
- Reset stale dispatch state if a card is manually moved back to `To-Do`
- Only auto-block an `In Progress` card after a real agent claim is visible in Trello
- Watchdog: If a `To-Do` card stays unclaimed for 15 minutes, notify Milton

## Trello API Proxy

Hermes agents use a Trello API proxy to perform write operations on the board
without needing their own API credentials. The proxy runs on Milton's machine
and is accessible via nginx at `https://141.148.88.85/trello-api/`.

### Available Endpoints

All endpoints are relative to `https://141.148.88.85/trello-api/`.

| Method | Path | Description | Required Fields |
|--------|------|-------------|-----------------|
| GET | /card/⟨shortLink⟩ | Read card details | — |
| PUT | /move-card | Move card to list | `cardId`, `listId` |
| PUT | /add-comment | Add comment | `cardId`, `text` |
| POST | /create-card | Create new card | `name`, `idList` (optional: `desc`) |
| POST | /add-label | Add label to card | `cardId`, `labelId` |
| POST | /list-labels | List board labels | — |
| POST | /list-lists | List board lists | — |

### Board Visibility

The Trello board is **Public** — any agent can read cards at the board URL
(`https://trello.com/b/Fi5EnmrN/jasons-goal-board`) without authentication.
Write operations require the API proxy.
