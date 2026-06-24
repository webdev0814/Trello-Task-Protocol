import { loadConfig } from "../lib/config.mjs";
import { buildInboxPayload } from "../lib/inbox-builder.mjs";
import { writeJson } from "../lib/fs-utils.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";
import { recordInboxItemsInState } from "../lib/board-workflow.mjs";

async function main() {
  const config = loadConfig();
  const state = await loadState(config.statePath);
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const { snapshot, payload } = await buildInboxPayload(client, config, {
    source: "poll",
    state,
    now: new Date(),
  });

  await writeJson(config.inboxPath, payload);

  state.board = snapshot.board;
  state.agent = snapshot.agent;

  for (const list of snapshot.context.lists) {
    for (const card of list.cards) {
      state.cards[card.id] = {
        ...(state.cards[card.id] || {}),
        cardName: card.name,
        listName: list.name,
        lastSeenDateLastActivity: card.dateLastActivity,
      };
    }
  }

  recordInboxItemsInState(state, payload.items, payload.generatedAt);
  await saveState(config.statePath, state);
  console.log(`Wrote inbox with ${payload.items.length} item(s) to ${config.inboxPath}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
