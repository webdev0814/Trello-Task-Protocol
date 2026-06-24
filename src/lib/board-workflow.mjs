import {
  buildActiveCardFollowUpComment,
  buildPromptContractComment,
  isContractComment,
} from "./prompt-contract.mjs";

function parseDateMs(value) {
  const ms = Date.parse(value || "");
  return Number.isFinite(ms) ? ms : null;
}

function summarizeComment(action) {
  if (!action) {
    return null;
  }

  return {
    id: action.id,
    date: action.date,
    author: action.memberCreator?.username || action.memberCreator?.fullName || null,
    text: action.data?.text || "",
  };
}

function byNewestActionFirst(left, right) {
  return new Date(right.date).getTime() - new Date(left.date).getTime();
}

function commentsByAgent(actions, agentMemberId) {
  return actions.filter((action) => action?.idMemberCreator === agentMemberId);
}

function commentsByHumans(actions, agentMemberId) {
  return actions.filter((action) => action?.idMemberCreator !== agentMemberId);
}

function buildStaleCardSignature(card, listName) {
  return `${listName}:${card.dateLastActivity || "unknown"}`;
}

function shouldQueueStaleCard({
  card,
  listName,
  stateCard,
  nowMs,
  staleAfterMs,
}) {
  const lastActivityMs = parseDateMs(card.dateLastActivity);
  if (!lastActivityMs) {
    return false;
  }

  if (nowMs - lastActivityMs < staleAfterMs) {
    return false;
  }

  const signature = buildStaleCardSignature(card, listName);
  const lastQueuedAtMs = parseDateMs(stateCard?.lastProactiveReviewQueuedAt);
  const lastQueuedSignature = stateCard?.lastProactiveReviewSignature || null;

  if (lastQueuedSignature !== signature) {
    return true;
  }

  if (!lastQueuedAtMs) {
    return true;
  }

  return nowMs - lastQueuedAtMs >= staleAfterMs;
}

export function createBoardContext({ board, lists, cardsByList, commentsByCard, agent }) {
  return {
    board,
    agent,
    lists: lists.map((list) => ({
      ...list,
      cards: (cardsByList[list.id] || []).map((card) => ({
        ...card,
        comments: (commentsByCard[card.id] || []).slice().sort(byNewestActionFirst),
      })),
    })),
  };
}

export function getCardInboxItems(context, options = {}) {
  const {
    state = null,
    now = new Date(),
    reviewIntervals = {
      todoMs: 24 * 60 * 60 * 1000,
      inProgressMs: 24 * 60 * 60 * 1000,
    },
  } = options;
  const items = [];
  const nowMs = now instanceof Date ? now.getTime() : Date.now();

  for (const list of context.lists) {
    for (const card of list.cards) {
      const stateCard = state?.cards?.[card.id] || null;
      const agentComments = commentsByAgent(card.comments, context.agent.id);
      const humanComments = commentsByHumans(card.comments, context.agent.id);
      const latestAgentComment = agentComments[0] || null;
      const latestHumanComment = humanComments[0] || null;
      const contractComment = agentComments.find(isContractComment) || null;
      const humanRespondedAfterAgent =
        latestAgentComment &&
        latestHumanComment &&
        new Date(latestHumanComment.date).getTime() >
          new Date(latestAgentComment.date).getTime();

      if (!contractComment) {
        items.push({
          kind: "missing_contract",
          cardId: card.id,
          cardName: card.name,
          listName: list.name,
          cardUrl: card.url,
          suggestedComment: buildPromptContractComment(card, list.name),
        });
        continue;
      }

      if (humanRespondedAfterAgent) {
        items.push({
          kind: "needs_review",
          reviewReason: "human_reply",
          proactive: false,
          cardId: card.id,
          cardName: card.name,
          listName: list.name,
          cardUrl: card.url,
          latestAgentComment: summarizeComment(latestAgentComment),
          latestHumanComment: summarizeComment(latestHumanComment),
        });
        continue;
      }

      if (
        list.name === "To-Do" &&
        shouldQueueStaleCard({
          card,
          listName: list.name,
          stateCard,
          nowMs,
          staleAfterMs: reviewIntervals.todoMs,
        })
      ) {
        items.push({
          kind: "needs_review",
          reviewReason: "todo_stale",
          proactive: true,
          cardId: card.id,
          cardName: card.name,
          listName: list.name,
          cardUrl: card.url,
          staleSince: card.dateLastActivity,
          latestAgentComment: summarizeComment(latestAgentComment),
          latestHumanComment: summarizeComment(latestHumanComment),
          suggestedComment: buildActiveCardFollowUpComment(card, list.name),
        });
        continue;
      }

      if (
        list.name === "In Progress" &&
        shouldQueueStaleCard({
          card,
          listName: list.name,
          stateCard,
          nowMs,
          staleAfterMs: reviewIntervals.inProgressMs,
        })
      ) {
        items.push({
          kind: "needs_review",
          reviewReason: "in_progress_stale",
          proactive: true,
          cardId: card.id,
          cardName: card.name,
          listName: list.name,
          cardUrl: card.url,
          staleSince: card.dateLastActivity,
          latestAgentComment: summarizeComment(latestAgentComment),
          latestHumanComment: summarizeComment(latestHumanComment),
          suggestedComment: buildActiveCardFollowUpComment(card, list.name),
        });
      }
    }
  }

  return items;
}

export function recordInboxItemsInState(state, items, generatedAt) {
  for (const item of items || []) {
    if (item.kind !== "needs_review" || !item.proactive) {
      continue;
    }

    state.cards[item.cardId] = {
      ...(state.cards[item.cardId] || {}),
      lastProactiveReviewQueuedAt: generatedAt,
      lastProactiveReviewReason: item.reviewReason || null,
      lastProactiveReviewSignature: buildStaleCardSignature(
        { dateLastActivity: item.staleSince || null },
        item.listName,
      ),
    };
  }
}
