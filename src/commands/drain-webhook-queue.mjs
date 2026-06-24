import { loadConfig } from "../lib/config.mjs";
import { writeJson } from "../lib/fs-utils.mjs";
import { buildInboxPayload } from "../lib/inbox-builder.mjs";
import { recordInboxItemsInState } from "../lib/board-workflow.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";
import { loadWebhookQueue, markWebhookQueueItemsProcessed } from "../lib/webhook-store.mjs";

async function main() {
  const config = loadConfig();
  const queue = await loadWebhookQueue(config.webhook.queuePath);

  if (!queue.pending.length) {
    await writeJson(config.webhook.inboxPath, {
      generatedAt: new Date().toISOString(),
      source: "webhook",
      board: null,
      agent: null,
      targetLists: config.trello.targetLists,
      triggerActions: [],
      items: [],
    });
    console.log(`No pending webhook events in ${config.webhook.queuePath}`);
    return;
  }

  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const cardIds = queue.pending.map((item) => item.cardId);
  const state = await loadState(config.statePath);
  const { snapshot, payload } = await buildInboxPayload(client, config, {
    cardIds,
    source: "webhook",
    triggerActions: queue.pending,
    state,
    now: new Date(),
  });

  await writeJson(config.webhook.inboxPath, payload);
  await markWebhookQueueItemsProcessed(
    config.webhook.queuePath,
    queue.pending.map((item) => item.actionId),
  );

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
  state.webhook.lastQueueDrainAt = new Date().toISOString();
  await saveState(config.statePath, state);

  console.log(
    `Wrote webhook inbox with ${payload.items.length} item(s) to ${config.webhook.inboxPath}`,
  );
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
