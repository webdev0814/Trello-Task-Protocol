import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadConfig } from "../lib/config.mjs";
import { readJson, writeJson } from "../lib/fs-utils.mjs";
import { loadState, saveState } from "../lib/state-store.mjs";

function countItems(payload) {
  return Array.isArray(payload?.items) ? payload.items.length : 0;
}

function hasOracleSync(config) {
  return Boolean(
    config.oracle.sshHost && config.oracle.sshUser && config.oracle.sshKeyPath && config.oracle.remoteDir,
  );
}

function runNodeCommand(scriptUrl, cwd) {
  const scriptPath = fileURLToPath(scriptUrl);
  const result = spawnSync(process.execPath, [scriptPath], {
    cwd,
    stdio: "pipe",
    encoding: "utf8",
  });

  if (result.status !== 0) {
    const stderr = result.stderr?.trim();
    const stdout = result.stdout?.trim();
    throw new Error(stderr || stdout || `${scriptPath} exited with status ${result.status}`);
  }

  return result.stdout?.trim() || "";
}

function getNextPollDueAt(lastPollAt, pollIntervalMs) {
  if (!lastPollAt) {
    return null;
  }

  const lastPollMs = Date.parse(lastPollAt);
  if (Number.isNaN(lastPollMs)) {
    return null;
  }

  return new Date(lastPollMs + pollIntervalMs).toISOString();
}

function isPollDue(lastPollAt, pollIntervalMs, nowMs) {
  if (!lastPollAt) {
    return true;
  }

  const lastPollMs = Date.parse(lastPollAt);
  if (Number.isNaN(lastPollMs)) {
    return true;
  }

  return nowMs - lastPollMs >= pollIntervalMs;
}

async function loadInbox(filePath) {
  return readJson(filePath, null);
}

async function main() {
  const config = loadConfig();
  const state = await loadState(config.statePath);
  const now = new Date();
  const nowIso = now.toISOString();
  const pollDue = isPollDue(state.reconciliation.lastPollAt, config.reconciliation.pollIntervalMs, now.getTime());
  const refresh = {
    generatedAt: nowIso,
    webhook: {
      attempted: true,
      mode: hasOracleSync(config) ? "oracle_sync" : "local_drain",
      ok: false,
      itemCount: 0,
      error: null,
    },
    poll: {
      attempted: false,
      due: pollDue,
      ok: false,
      itemCount: 0,
      error: null,
      lastPollAt: state.reconciliation.lastPollAt,
      nextDueAt: getNextPollDueAt(state.reconciliation.lastPollAt, config.reconciliation.pollIntervalMs),
    },
    selectedSource: "none",
    selectedReason: "no_items",
  };

  let webhookInbox = null;
  let selectedInbox = null;

  try {
    const webhookScript = hasOracleSync(config)
      ? new URL("./sync-oracle-webhook-inbox.mjs", import.meta.url)
      : new URL("./drain-webhook-queue.mjs", import.meta.url);

    runNodeCommand(webhookScript, config.cwd);
    webhookInbox = await loadInbox(config.webhook.inboxPath);
    refresh.webhook.ok = true;
    refresh.webhook.itemCount = countItems(webhookInbox);
  } catch (error) {
    refresh.webhook.error = error.message;
  }

  if (countItems(webhookInbox) > 0) {
    selectedInbox = webhookInbox;
    refresh.selectedSource = "webhook";
    refresh.selectedReason = "webhook_items";
  } else if (pollDue) {
    refresh.poll.attempted = true;

    try {
      runNodeCommand(new URL("./poll-once.mjs", import.meta.url), config.cwd);
      const pollInbox = await loadInbox(config.inboxPath);
      refresh.poll.ok = true;
      refresh.poll.itemCount = countItems(pollInbox);
      state.reconciliation.lastPollAt = new Date().toISOString();
      await saveState(config.statePath, state);
      refresh.poll.lastPollAt = state.reconciliation.lastPollAt;
      refresh.poll.nextDueAt = getNextPollDueAt(
        state.reconciliation.lastPollAt,
        config.reconciliation.pollIntervalMs,
      );
      selectedInbox = pollInbox;
      refresh.selectedSource = "poll";
      refresh.selectedReason = "reconciliation_due";
    } catch (error) {
      refresh.poll.error = error.message;
      refresh.selectedReason = refresh.webhook.error ? "webhook_failed_poll_failed" : "poll_failed";
    }
  } else {
    refresh.selectedSource = "webhook";
    refresh.selectedReason = "webhook_empty_poll_not_due";
  }

  const activeInbox = {
    generatedAt: nowIso,
    source: selectedInbox?.source || refresh.selectedSource,
    board: selectedInbox?.board || webhookInbox?.board || null,
    agent: selectedInbox?.agent || webhookInbox?.agent || null,
    targetLists: selectedInbox?.targetLists || webhookInbox?.targetLists || config.trello.targetLists,
    triggerActions: selectedInbox?.triggerActions || webhookInbox?.triggerActions || [],
    items: selectedInbox?.items || [],
    refresh,
  };

  await writeJson(config.activeInboxPath, activeInbox);

  console.log(
    JSON.stringify(
      {
        activeInboxPath: config.activeInboxPath,
        selectedSource: refresh.selectedSource,
        selectedReason: refresh.selectedReason,
        itemCount: activeInbox.items.length,
        webhook: refresh.webhook,
        poll: refresh.poll,
      },
      null,
      2,
    ),
  );
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
