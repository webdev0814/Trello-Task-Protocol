import { parseArgs } from "../lib/cli.mjs";
import { loadConfig } from "../lib/config.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";

async function main() {
  const args = parseArgs();
  const webhookId = args.id || args.webhook;

  if (!webhookId) {
    throw new Error("Provide --id <webhook-id>.");
  }

  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  await client.deleteTokenWebhook(webhookId);

  const state = await loadState(config.statePath);
  state.webhook.registrations = (state.webhook.registrations || []).filter(
    (entry) => entry.id !== webhookId,
  );
  await saveState(config.statePath, state);

  console.log(`Deleted webhook ${webhookId}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
