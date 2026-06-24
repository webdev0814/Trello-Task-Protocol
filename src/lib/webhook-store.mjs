import { readJson, writeJson } from "./fs-utils.mjs";

const MAX_EVENT_LOG = 500;
const MAX_ACTION_HISTORY = 1000;

function createDefaultQueue() {
  return {
    version: 1,
    updatedAt: null,
    pending: [],
    recentActionIds: [],
  };
}

function createDefaultEventLog() {
  return {
    version: 1,
    updatedAt: null,
    events: [],
  };
}

function uniqueTail(values, maxLength) {
  return [...new Set(values)].slice(-maxLength);
}

export async function loadWebhookQueue(queuePath) {
  return (await readJson(queuePath, createDefaultQueue())) || createDefaultQueue();
}

export async function enqueueWebhookQueueItem(queuePath, item) {
  const queue = await loadWebhookQueue(queuePath);
  const actionId = item.actionId;
  const duplicate =
    queue.pending.some((entry) => entry.actionId === actionId) ||
    queue.recentActionIds.includes(actionId);

  if (duplicate) {
    return {
      enqueued: false,
      reason: "duplicate_action",
      queue,
    };
  }

  queue.pending.push(item);
  queue.updatedAt = new Date().toISOString();
  await writeJson(queuePath, queue);

  return {
    enqueued: true,
    reason: null,
    queue,
  };
}

export async function markWebhookQueueItemsProcessed(queuePath, actionIds) {
  const queue = await loadWebhookQueue(queuePath);
  const actionIdSet = new Set(actionIds);
  queue.pending = queue.pending.filter((entry) => !actionIdSet.has(entry.actionId));
  queue.recentActionIds = uniqueTail(
    [...queue.recentActionIds, ...actionIds.filter(Boolean)],
    MAX_ACTION_HISTORY,
  );
  queue.updatedAt = new Date().toISOString();
  await writeJson(queuePath, queue);
  return queue;
}

export async function appendWebhookEvent(eventLogPath, event) {
  const eventLog = (await readJson(eventLogPath, createDefaultEventLog())) || createDefaultEventLog();
  eventLog.events.push(event);
  eventLog.events = eventLog.events.slice(-MAX_EVENT_LOG);
  eventLog.updatedAt = new Date().toISOString();
  await writeJson(eventLogPath, eventLog);
  return eventLog;
}
