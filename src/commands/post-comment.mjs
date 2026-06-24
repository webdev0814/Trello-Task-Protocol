import { parseArgs, readCommentBody } from "../lib/cli.mjs";
import { loadConfig } from "../lib/config.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";

async function main() {
  const args = parseArgs();
  const cardId = args.card;

  if (!cardId) {
    throw new Error("Provide --card <card-id>.");
  }

  const text = (await readCommentBody({ text: args.text, textFile: args["text-file"] })).trim();
  if (!text) {
    throw new Error("Comment body was empty.");
  }

  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  await client.addComment(cardId, text);
  console.log(`Posted comment to card ${cardId}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
