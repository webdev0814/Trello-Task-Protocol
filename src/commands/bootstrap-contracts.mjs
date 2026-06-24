import { loadConfig } from "../lib/config.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";
import { TrelloClient } from "../lib/trello-api.mjs";
import { buildPromptContractComment, isContractComment } from "../lib/prompt-contract.mjs";

async function main() {
  const config = loadConfig();
  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const [agent, board, lists] = await Promise.all([
    client.getMe(),
    client.getBoard(config.trello.boardRef),
    client.getBoardLists(config.trello.boardRef),
  ]);

  const targetLists = lists.filter((list) => config.trello.targetLists.includes(list.name));
  const state = await loadState(config.statePath);
  state.board = board;
  state.agent = agent;

  let posted = 0;
  let skipped = 0;

  for (const list of targetLists) {
    const cards = await client.getCardsForList(list.id);

    for (const card of cards) {
      const comments = await client.getCardComments(card.id, 100);
      const hasExistingContract = comments.some(
        (comment) => comment.idMemberCreator === agent.id && isContractComment(comment),
      );

      if (hasExistingContract) {
        skipped += 1;
        continue;
      }

      const commentText = buildPromptContractComment(card, list.name);
      const created = await client.addComment(card.id, commentText);
      state.cards[card.id] = {
        cardName: card.name,
        listName: list.name,
        lastContractCommentId: created?.id || null,
        lastSeenDateLastActivity: card.dateLastActivity,
      };
      posted += 1;
    }
  }

  await saveState(config.statePath, state);
  console.log(`Posted ${posted} prompt contract comment(s); skipped ${skipped}.`);
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
