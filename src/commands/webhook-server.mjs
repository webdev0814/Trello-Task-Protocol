import http from "node:http";
import { loadConfig } from "../lib/config.mjs";
import { resolveBoardId } from "../lib/board-id.mjs";
import { loadState } from "../lib/state-store.mjs";
import { appendWebhookEvent, enqueueWebhookQueueItem } from "../lib/webhook-store.mjs";
import { normalizeWebhookAction, verifyWebhookSignature } from "../lib/webhook-utils.mjs";

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  response.end(`${JSON.stringify(payload)}\n`);
}

async function readRawBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

async function resolveAgentMemberId(config) {
  if (config.trello.agentMemberId) {
    return config.trello.agentMemberId;
  }

  const state = await loadState(config.statePath);
  return state.agent?.id || "";
}

async function main() {
  const config = loadConfig();
  const agentMemberId = await resolveAgentMemberId(config);
  const boardId = await resolveBoardId(config);

  const server = http.createServer(async (request, response) => {
    const requestUrl = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);

    if (requestUrl.pathname !== config.webhook.path) {
      sendJson(response, 404, { ok: false, error: "not_found" });
      return;
    }

    if (request.method === "HEAD") {
      response.writeHead(200);
      response.end();
      return;
    }

    if (request.method === "GET") {
      sendJson(response, 200, {
        ok: true,
        path: config.webhook.path,
        callbackUrl: config.webhook.callbackUrl,
        queuePath: config.webhook.queuePath,
        eventLogPath: config.webhook.eventLogPath,
      });
      return;
    }

    if (request.method !== "POST") {
      sendJson(response, 405, { ok: false, error: "method_not_allowed" });
      return;
    }

    try {
      const rawBody = await readRawBody(request);
      const signature = request.headers["x-trello-webhook"];
      const verified = verifyWebhookSignature(
        rawBody,
        Array.isArray(signature) ? signature[0] : signature,
        config.trello.apiSecret,
        config.webhook.callbackUrl,
      );

      if (!verified) {
        sendJson(response, 401, { ok: false, error: "invalid_signature" });
        return;
      }

      const payload = JSON.parse(rawBody);
      const normalized = normalizeWebhookAction(payload, {
        boardId,
        agentMemberId,
      });

      await appendWebhookEvent(config.webhook.eventLogPath, {
        receivedAt: new Date().toISOString(),
        verified,
        relevant: normalized.relevant,
        ignoredReason: normalized.reason,
        actionId: payload?.action?.id || null,
        actionType: payload?.action?.type || null,
        payload,
      });

      if (!normalized.relevant || !normalized.item) {
        sendJson(response, 200, {
          ok: true,
          accepted: false,
          ignoredReason: normalized.reason,
        });
        return;
      }

      const queued = await enqueueWebhookQueueItem(config.webhook.queuePath, normalized.item);
      sendJson(response, 200, {
        ok: true,
        accepted: true,
        enqueued: queued.enqueued,
        ignoredReason: queued.reason,
        actionId: normalized.item.actionId,
        cardId: normalized.item.cardId,
      });
    } catch (error) {
      sendJson(response, 500, {
        ok: false,
        error: "server_error",
        message: error.message,
      });
    }
  });

  server.listen(config.webhook.port, config.webhook.host, () => {
    console.log(
      `Trello webhook server listening on http://${config.webhook.host}:${config.webhook.port}${config.webhook.path}`,
    );
    console.log(`Expected callback URL for signature verification: ${config.webhook.callbackUrl}`);
  });
}

main().catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
