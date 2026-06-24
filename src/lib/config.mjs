import path from "node:path";
import { loadLocalEnv } from "./env.mjs";

function parseBoardRef(boardUrlOrId) {
  if (!boardUrlOrId) {
    throw new Error("Set TRELLO_BOARD_URL or a board shortlink in .env.local.");
  }

  if (/^https?:\/\//i.test(boardUrlOrId)) {
    const url = new URL(boardUrlOrId);
    const match = url.pathname.match(/^\/b\/([^/]+)/i);
    if (!match) {
      throw new Error(`Could not parse Trello board shortlink from ${boardUrlOrId}.`);
    }
    return match[1];
  }

  return boardUrlOrId;
}

function parseListNames(value) {
  return (value || "To-Do,In Progress,Blocked,Done")
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function normalizeWebhookPath(value) {
  if (!value) {
    return "/trello/webhook";
  }

  return value.startsWith("/") ? value : `/${value}`;
}

function requireValue(name, value) {
  if (!value) {
    throw new Error(`Missing required config: ${name}`);
  }
  return value;
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(value || "", 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return fallback;
}

export function loadConfig() {
  loadLocalEnv();

  const cwd = process.cwd();
  const boardUrl = process.env.TRELLO_BOARD_URL || "";
  const webhookHost = process.env.TRELLO_WEBHOOK_HOST || "127.0.0.1";
  const webhookPort = Number.parseInt(process.env.TRELLO_WEBHOOK_PORT || "8787", 10);
  const webhookPath = normalizeWebhookPath(process.env.TRELLO_WEBHOOK_PATH || "/trello/webhook");
  const webhookCallbackUrl =
    process.env.TRELLO_WEBHOOK_CALLBACK_URL || `http://localhost:${webhookPort}${webhookPath}`;

  return {
    cwd,
    dataDir: path.join(cwd, "data"),
    activeInboxPath: path.join(cwd, "data", "trello-active-inbox.json"),
    snapshotPath: path.join(cwd, "data", "board-snapshot.json"),
    inboxPath: path.join(cwd, "data", "trello-inbox.json"),
    statePath: path.join(cwd, "data", "trello-agent-state.json"),
    webhookInboxPath: path.join(cwd, "data", "trello-webhook-inbox.json"),
    trello: {
      apiKey: requireValue("TRELLO_API_KEY", process.env.TRELLO_API_KEY),
      apiSecret: process.env.TRELLO_API_SECRET || "",
      token: process.env.TRELLO_TOKEN || "",
      boardRef: parseBoardRef(boardUrl || process.env.TRELLO_BOARD_ID || ""),
      boardUrl,
      targetLists: parseListNames(process.env.TRELLO_TARGET_LISTS),
      agentUsername: process.env.TRELLO_AGENT_USERNAME || "",
      agentMemberId: process.env.TRELLO_AGENT_MEMBER_ID || "",
    },
    webhook: {
      host: webhookHost,
      port: webhookPort,
      path: webhookPath,
      callbackUrl: webhookCallbackUrl,
      description: process.env.TRELLO_WEBHOOK_DESCRIPTION || "Codex Trello Board Webhook",
      queuePath: path.join(cwd, "data", "trello-webhook-queue.json"),
      inboxPath: path.join(cwd, "data", "trello-webhook-inbox.json"),
      eventLogPath: path.join(cwd, "data", "trello-webhook-events.json"),
    },
    oracle: {
      sshHost: process.env.ORACLE_TRELLO_SSH_HOST || "",
      sshUser: process.env.ORACLE_TRELLO_SSH_USER || "ubuntu",
      sshKeyPath: process.env.ORACLE_TRELLO_SSH_KEY_PATH || "",
      remoteDir: process.env.ORACLE_TRELLO_REMOTE_DIR || "",
    },
    reconciliation: {
      pollIntervalHours: parsePositiveInt(process.env.TRELLO_RECONCILIATION_POLL_INTERVAL_HOURS, 12),
      pollIntervalMs:
        parsePositiveInt(process.env.TRELLO_RECONCILIATION_POLL_INTERVAL_HOURS, 12) * 60 * 60 * 1000,
    },
    reviewIntervals: {
      todoHours: parsePositiveInt(process.env.TRELLO_TODO_REVIEW_INTERVAL_HOURS, 24),
      todoMs: parsePositiveInt(process.env.TRELLO_TODO_REVIEW_INTERVAL_HOURS, 24) * 60 * 60 * 1000,
      inProgressHours: parsePositiveInt(process.env.TRELLO_IN_PROGRESS_REVIEW_INTERVAL_HOURS, 24),
      inProgressMs:
        parsePositiveInt(process.env.TRELLO_IN_PROGRESS_REVIEW_INTERVAL_HOURS, 24) * 60 * 60 * 1000,
    },
    pollIntervalMs: Number.parseInt(process.env.POLL_INTERVAL_MS || "300000", 10),
  };
}
