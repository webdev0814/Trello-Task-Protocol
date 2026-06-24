import { loadConfig } from "../lib/config.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";

async function main() {
  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const hooks = await client.listTokenWebhooks();
  console.log(JSON.stringify(hooks, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
