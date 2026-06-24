import { parseArgs } from "../lib/cli.mjs";
import { loadConfig } from "../lib/config.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";

async function main() {
  const args = parseArgs();
  const cardId = args.card;
  const targetListName = args.list;

  if (!cardId) {
    throw new Error("Provide --card <card-id>.");
  }

  if (!targetListName) {
    throw new Error('Provide --list "List Name".');
  }

  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const lists = await client.getBoardLists(config.trello.boardRef);
  const targetList = lists.find((list) => list.name === targetListName);

  if (!targetList) {
    throw new Error(`Could not find Trello list named "${targetListName}".`);
  }

  await client.moveCardToList(cardId, targetList.id);
  console.log(`Moved card ${cardId} to ${targetListName}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
