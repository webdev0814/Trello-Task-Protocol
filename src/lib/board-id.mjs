import { loadState } from "./state-store.mjs";
import { TrelloClient } from "./trello-api.mjs";

export async function resolveBoardId(config) {
  const state = await loadState(config.statePath);
  if (state.board?.id) {
    return state.board.id;
  }

  const client = new TrelloClient({
    apiKey: config.trello.apiKey,
    token: config.trello.token,
  });

  const board = await client.getBoard(config.trello.boardRef);
  return board.id;
}
