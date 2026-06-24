import crypto from "node:crypto";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1"]);

function safeEqual(left, right) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);

  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }

  return crypto.timingSafeEqual(leftBuffer, rightBuffer);
}

export function buildWebhookSignature(rawBody, secret, callbackUrl) {
  return crypto
    .createHmac("sha1", secret)
    .update(rawBody + callbackUrl)
    .digest("base64");
}

export function verifyWebhookSignature(rawBody, headerValue, secret, callbackUrl) {
  if (!headerValue || !secret || !callbackUrl) {
    return false;
  }

  const expected = buildWebhookSignature(rawBody, secret, callbackUrl);
  return safeEqual(expected, headerValue);
}

export function isPublicCallbackUrl(value) {
  if (!value) {
    return false;
  }

  let url;
  try {
    url = new URL(value);
  } catch {
    return false;
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return false;
  }

  return !LOCAL_HOSTS.has(url.hostname);
}

export function normalizeWebhookAction(payload, { boardId, agentMemberId }) {
  const action = payload?.action;
  const model = payload?.model;
  const card = action?.data?.card;
  const actionBoardId = action?.data?.board?.id || model?.id || null;
  const creatorId = action?.idMemberCreator || action?.memberCreator?.id || null;

  if (!action?.id) {
    return {
      relevant: false,
      reason: "missing_action",
      item: null,
    };
  }

  if (actionBoardId !== boardId) {
    return {
      relevant: false,
      reason: "wrong_board",
      item: null,
    };
  }

  if (!card?.id) {
    return {
      relevant: false,
      reason: "not_card_action",
      item: null,
    };
  }

  if (agentMemberId && creatorId === agentMemberId) {
    return {
      relevant: false,
      reason: "agent_action",
      item: null,
    };
  }

  return {
    relevant: true,
    reason: null,
    item: {
      actionId: action.id,
      actionType: action.type || "unknown",
      actionDate: action.date || null,
      boardId: actionBoardId,
      cardId: card.id,
      cardName: card.name || "",
      creatorId,
      creatorUsername: action?.memberCreator?.username || "",
      creatorFullName: action?.memberCreator?.fullName || "",
      listBeforeName: action?.data?.listBefore?.name || null,
      listAfterName: action?.data?.listAfter?.name || action?.data?.list?.name || null,
      receivedAt: new Date().toISOString(),
      source: "trello_webhook",
    },
  };
}
