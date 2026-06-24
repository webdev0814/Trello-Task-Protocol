import { parseArgs } from "../lib/cli.mjs";
import { resolveBoardId } from "../lib/board-id.mjs";
import { loadConfig } from "../lib/config.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";
import { isPublicCallbackUrl } from "../lib/webhook-utils.mjs";

async function main() {
  const args = parseArgs();
  const config = loadConfig();
  const callbackUrl = args["callback-url"] || config.webhook.callbackUrl;
  const description = args.description || config.webhook.description;

  if (!isPublicCallbackUrl(callbackUrl)) {
    throw new Error(
      "Webhook registration requires a public HTTPS callback URL. Update TRELLO_WEBHOOK_CALLBACK_URL or pass --callback-url.",
    );
  }

  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });
  const boardId = await resolveBoardId(config);

  const created = await client.createTokenWebhook({
    callbackURL: callbackUrl,
    idModel: boardId,
    description,
  });

  const state = await loadState(config.statePath);
  state.webhook.registrations = [
    ...(state.webhook.registrations || []).filter((entry) => entry.id !== created.id),
    {
      id: created.id,
      callbackURL: created.callbackURL,
      idModel: created.idModel,
      description: created.description || description,
      active: created.active,
      createdAt: new Date().toISOString(),
    },
  ];
  await saveState(config.statePath, state);

  console.log(JSON.stringify(created, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
