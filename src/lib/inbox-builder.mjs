import { createBoardContext, getCardInboxItems } from "./board-workflow.mjs";

async function loadBoardBase(client, config) {
  const [agent, board, lists] = await Promise.all([
    client.getMe(),
    client.getBoard(config.trello.boardRef),
    client.getBoardLists(config.trello.boardRef),
  ]);

  const targetLists = lists.filter((list) => config.trello.targetLists.includes(list.name));
  return {
    agent,
    board,
    lists,
    targetLists,
  };
}

async function loadCardsForTargetLists(client, targetLists) {
  const cardsByList = {};
  const commentsByCard = {};

  for (const list of targetLists) {
    const cards = await client.getCardsForList(list.id);
    cardsByList[list.id] = cards;

    for (const card of cards) {
      commentsByCard[card.id] = await client.getCardComments(card.id, 100);
    }
  }

  return {
    cardsByList,
    commentsByCard,
    listsForContext: targetLists,
  };
}

async function loadSpecificCards(client, targetLists, cardIds) {
  const cardsByList = {};
  const commentsByCard = {};
  const targetListsById = new Map(targetLists.map((list) => [list.id, list]));

  const uniqueCardIds = [...new Set(cardIds)];
  const cards = [];

  for (const cardId of uniqueCardIds) {
    try {
      const card = await client.getCard(cardId);
      if (!card.closed && targetListsById.has(card.idList)) {
        cards.push(card);
      }
    } catch (error) {
      if (!String(error.message || "").includes("404")) {
        throw error;
      }
    }
  }

  for (const card of cards) {
    if (!cardsByList[card.idList]) {
      cardsByList[card.idList] = [];
    }
    cardsByList[card.idList].push(card);
    commentsByCard[card.id] = await client.getCardComments(card.id, 100);
  }

  const listsForContext = targetLists.filter((list) => (cardsByList[list.id] || []).length > 0);
  return {
    cardsByList,
    commentsByCard,
    listsForContext,
  };
}

export async function buildBoardSnapshot(client, config, { cardIds = null } = {}) {
  const base = await loadBoardBase(client, config);
  const loaded = cardIds?.length
    ? await loadSpecificCards(client, base.targetLists, cardIds)
    : await loadCardsForTargetLists(client, base.targetLists);

  const context = createBoardContext({
    board: base.board,
    lists: loaded.listsForContext,
    cardsByList: loaded.cardsByList,
    commentsByCard: loaded.commentsByCard,
    agent: base.agent,
  });

  return {
    board: base.board,
    agent: base.agent,
    lists: base.targetLists,
    context,
  };
}

export async function buildInboxPayload(
  client,
  config,
  { cardIds = null, source = "poll", triggerActions = [], state = null, now = new Date() } = {},
) {
  const snapshot = await buildBoardSnapshot(client, config, { cardIds });
  const items = getCardInboxItems(snapshot.context, {
    state,
    now,
    reviewIntervals: config.reviewIntervals,
  });

  return {
    snapshot,
    payload: {
      generatedAt: new Date().toISOString(),
      source,
      board: snapshot.board,
      agent: snapshot.agent,
      targetLists: config.trello.targetLists,
      triggerActions,
      items,
    },
  };
}
