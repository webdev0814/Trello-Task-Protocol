import { loadConfig } from "../lib/config.mjs";
import { writeJson } from "../lib/fs-utils.mjs";
import { buildBoardSnapshot } from "../lib/inbox-builder.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";

async function main() {
  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const snapshot = await buildBoardSnapshot(client, config);
  await writeJson(config.snapshotPath, snapshot.context);
  console.log(`Wrote board snapshot to ${config.snapshotPath}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
