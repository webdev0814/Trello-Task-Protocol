#!/usr/bin/env python3
"""Webhook Receiver — Forwards Trello + Jira updates to assigned agents via Telegram.
   Also serves as a Trello API proxy for Hermes agents."""

import json, os, sys, hmac, hashlib, re, logging
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webhook-server")

# Trello board constants
BOARD_ID = "Fi5EnmrN"
TRELLO_PROXY_BASE = "https://141.148.88.85/trello-api"

# Load creds
CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")
TRELLO_KEY = TRELLO_TOKEN = None
PROXY_SECRET_PATH = os.path.expanduser("~/.openclaw/trello_proxy_secret")
PROXY_SECRET = None
try:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    TRELLO_KEY = cfg.get("env", {}).get("TRELLO_API_KEY")
    TRELLO_TOKEN = cfg.get("env", {}).get("TRELLO_TOKEN")
except Exception as e:
    log.error(f"Cannot load config: {e}")

try:
    with open(PROXY_SECRET_PATH) as f:
        PROXY_SECRET = f.read().strip()
except Exception as e:
    log.error(f"Cannot load Trello proxy secret: {e}")

# Agent emoji -> Telegram target mapping
AGENT_ROUTES = {
    "\U0001f43b": ("Pam \U0001f43b", "telegram:8376220728"),
    "\U0001f3c0": ("Jim \U0001f3c0", "docker_exec"),
    "\U0001f9ee": ("Kevin \U0001f9ee", "telegram_bot:8611819855:AAFnGETm3pbkjErL0g-gnN-JZ3S9l5N09rs:8376220728"),
    "\U0001f3a4": ("Michael \U0001f3a4", "paperclip"),
    "\U0001f3c3": ("Dwight \U0001f3c3", "paperclip"),
}

# Trello label name -> agent mapping
LABEL_TO_AGENT = {
    "Pam \U0001f43b": "\U0001f43b",
    "Michael \U0001f3a4": "\U0001f3a4",
    "Jim \U0001f3c0": "\U0001f3c0",
    "Dwight \U0001f3c3": "\U0001f3c3",
    "Kevin \U0001f9ee": "\U0001f9ee",
}

AGENT_LABELS = {
    "jason": ("Jason", "6a0f56ebba3a41946dd7499b"),
    "pam": ("Pam", "69f9fbaf82c748c09954c907"),
    "pam beesly": ("Pam", "69f9fbaf82c748c09954c907"),
    "michael": ("Michael", "69f9fbb06314b722effa005c"),
    "kevin": ("Kevin", "69fe110d10bd665905019680"),
    "dwight": ("Dwight", "69f9fbb0472161ddc71320a6"),
    "milton": ("Milton", "69f9fbafd289bfdc755103b6"),
}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_agent(value):
    key = str(value or "").strip().lower()
    return AGENT_LABELS.get(key)


def attribution_block(agent, action):
    return f"Agent: {agent}\nAction: {action}\nAt: {utc_now()}"


def attributed_comment(agent, action, text):
    body = str(text or "").strip()
    return f"{attribution_block(agent, action)}\n\n{body}"


def attributed_description(agent, source, desc):
    body = str(desc or "").strip()
    created = (
        f"Created by: {agent}\n"
        f"Created via: {source or 'Trello API proxy'}\n"
        f"Created at: {utc_now()}"
    )
    return f"{created}\n\n---\n\n{body}" if body else created


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler with webhook receiver + Trello API proxy endpoints."""

    # ======================================================================
    #  TRELLO API PROXY  (accessible to Hermes agents via nginx)
    # ======================================================================

    def _trello_api(self, method, path_suffix, data=None):
        """Proxy a Trello API call using stored credentials."""
        if not TRELLO_KEY or not TRELLO_TOKEN:
            return {"error": "Trello credentials not configured on server"}, 500
        sep = "&" if "?" in path_suffix else "?"
        url = f"https://api.trello.com/1{path_suffix}{sep}key={TRELLO_KEY}&token={TRELLO_TOKEN}"
        req = Request(url, data=data, method=method,
                      headers={"Content-Type": "application/json"} if data else {})
        try:
            resp = urlopen(req, timeout=15)
            body = resp.read()
            return json.loads(body) if body else {}, resp.status
        except Exception as e:
            log.error(f"Trello API error ({method} {path_suffix}): {e}")
            return {"error": str(e)}, getattr(e, "code", 500)

    def _send_json(self, status_code, data):
        body = json.dumps(data).encode()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _require_proxy_secret(self):
        if not PROXY_SECRET:
            self._send_json(500, {"error": "Trello proxy secret not configured"})
            return False
        supplied = self.headers.get("X-Proxy-Agent-Secret", "")
        if not hmac.compare_digest(supplied, PROXY_SECRET):
            self._send_json(403, {"error": "valid X-Proxy-Agent-Secret header required"})
            return False
        return True

    def _label_id_for_name(self, value):
        if not value:
            return None
        agent_info = normalize_agent(value)
        if agent_info:
            return agent_info[1]
        wanted = str(value).strip().lower()
        result, status = self._trello_api("GET", f"/boards/{BOARD_ID}/labels?fields=name,id,color")
        if status != 200:
            return None
        for label in result:
            if (label.get("name") or "").strip().lower() == wanted:
                return label.get("id")
        return None

    # ---- GET ----
    def do_GET(self):
        m = re.match(r"^/trello-api/card/([a-zA-Z0-9]+)$", self.path)
        if m:
            short_link = m.group(1)
            data, status = self._trello_api(
                "GET",
                f"/cards/{short_link}?fields=name,desc,idList,url,shortLink&labels=all"
            )
            self._send_json(status, data)
            return
        # Health check
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"OK")

    # ---- PUT ----
    def do_PUT(self):
        if not self.path.startswith("/trello-api/"):
            self._send_json(404, {"error": "not found"})
            return
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b""
        log.info(f"PUT {self.path}: {len(body)} bytes")
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except:
            self._send_json(400, {"error": "invalid JSON"})
            return

        # PUT /trello-api/move-card
        if self.path == "/trello-api/move-card":
            if not self._require_proxy_secret():
                return
            card_id = data.get("cardId") or data.get("id")
            list_id = data.get("listId") or data.get("idList")
            if not card_id or not list_id:
                self._send_json(400, {"error": "cardId and listId required"})
                return
            payload = json.dumps({"idList": list_id}).encode()
            result, status = self._trello_api("PUT", f"/cards/{card_id}", payload)
            self._send_json(status, result)
            return

        # PUT /trello-api/add-label
        if self.path == "/trello-api/add-label":
            if not self._require_proxy_secret():
                return
            card_id = data.get("cardId") or data.get("id")
            label_id = data.get("labelId") or self._label_id_for_name(data.get("labelName"))
            if not card_id or not label_id:
                self._send_json(400, {"error": "cardId and labelId or labelName required"})
                return
            result, status = self._trello_api(
                "POST", f"/cards/{card_id}/idLabels",
                json.dumps({"value": label_id}).encode()
            )
            self._send_json(status, result)
            return

        # PUT /trello-api/add-comment
        if self.path == "/trello-api/add-comment":
            if not self._require_proxy_secret():
                return
            card_id = data.get("cardId") or data.get("id")
            text = data.get("text")
            agent_info = normalize_agent(data.get("agent"))
            action = data.get("action", "Comment")
            if not card_id or not text or not agent_info:
                self._send_json(400, {"error": "cardId, text, and valid agent required"})
                return
            agent, _label_id = agent_info
            payload = json.dumps({"text": attributed_comment(agent, action, text)}).encode()
            result, status = self._trello_api(
                "POST", f"/cards/{card_id}/actions/comments", payload
            )
            self._send_json(status, result)
            return

        # PUT /trello-api/close-card
        if self.path == "/trello-api/close-card":
            if not self._require_proxy_secret():
                return
            card_id = data.get("cardId") or data.get("id")
            closed = data.get("closed", True)
            if not card_id:
                self._send_json(400, {"error": "cardId required"})
                return
            payload = json.dumps({"closed": bool(closed)}).encode()
            result, status = self._trello_api("PUT", f"/cards/{card_id}", payload)
            self._send_json(status, result)
            return

        self._send_json(404, {"error": "unknown endpoint"})

    # ---- POST ----
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        log.info(f"POST {self.path}: {len(body)} bytes")

        # --- Trello API proxy endpoints ---
        # POST /trello-api/create-card
        if self.path == "/trello-api/create-card":
            if not self._require_proxy_secret():
                return
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except:
                self._send_json(400, {"error": "invalid JSON"})
                return
            name = data.get("name", "New Task")
            desc = data.get("desc", "")
            id_list = data.get("idList") or data.get("listId")
            agent_info = normalize_agent(data.get("agent"))
            if not id_list or not agent_info:
                self._send_json(400, {"error": "idList and valid agent required"})
                return
            agent, label_id = agent_info
            source = data.get("source", "Trello API proxy")
            payload = json.dumps({
                "name": name,
                "desc": attributed_description(agent, source, desc),
                "idList": id_list,
                "idLabels": label_id,
            }).encode()
            result, status = self._trello_api("POST", "/cards", payload)
            self._send_json(status, result)
            return

        # POST /trello-api/add-label
        if self.path == "/trello-api/add-label":
            if not self._require_proxy_secret():
                return
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except:
                self._send_json(400, {"error": "invalid JSON"})
                return
            card_id = data.get("cardId") or data.get("id")
            label_id = data.get("labelId") or self._label_id_for_name(data.get("labelName"))
            if not card_id or not label_id:
                self._send_json(400, {"error": "cardId and labelId or labelName required"})
                return
            result, status = self._trello_api(
                "POST", f"/cards/{card_id}/idLabels",
                json.dumps({"value": label_id}).encode()
            )
            self._send_json(status, result)
            return

        # POST /trello-api/list-labels
        if self.path == "/trello-api/list-labels":
            result, status = self._trello_api(
                "GET", f"/boards/{BOARD_ID}/labels?fields=name,id,color"
            )
            self._send_json(status, result)
            return

        # POST /trello-api/list-lists
        if self.path == "/trello-api/list-lists":
            result, status = self._trello_api(
                "GET", f"/boards/{BOARD_ID}/lists?fields=name,id"
            )
            self._send_json(status, result)
            return

        # POST /trello-api/creds/get
        if self.path == "/trello-api/creds/get":
            if not self._require_proxy_secret():
                return
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except:
                self._send_json(400, {"error": "invalid JSON"})
                return
            raw = data.get("name", "")
            # Normalize: lowercase with underscores to uppercase env var names
            norm = raw.strip().upper()
            config_path = os.path.expanduser("~/.openclaw/openclaw.json")
            try:
                with open(config_path) as f:
                    cfg = json.load(f)
                env = cfg.get("env", {})
                value = None
                secret_paths = {
                    "TRELLO_PROXY_SECRET": "~/.openclaw/trello_proxy_secret",
                    "GCLOUD_SERVICE_ACCOUNT_KEY": "~/.openclaw/credentials/drive-key.json",
                }
                if norm in secret_paths:
                    spath = os.path.expanduser(secret_paths[norm])
                    if os.path.exists(spath):
                        with open(spath) as f:
                            value = f.read().strip()
                elif norm in env:
                    value = env[norm]
                if value is None:
                    self._send_json(404, {"error": f"Unknown credential: {raw}"})
                    return
                self._send_json(200, {"name": raw, "value": value})
            except Exception as e:
                log.error(f"Error reading credential '{raw}': {e}")
                self._send_json(500, {"error": str(e)})
            return

        # --- Original Trello / Jira webhook handling ---
        try:
            data = json.loads(body.decode("utf-8"))
            if self.path.startswith("/jira-webhook"):
                self._process_jira_update(data)
            elif self.path.startswith("/trello-webhook"):
                self._process_trello_update(data)
        except Exception as e:
            log.error(f"Parse error: {e}")

        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"OK")

    # ======================================================================
    #  JIRA HANDLER
    # ======================================================================
    def _process_jira_update(self, data):
        webhook_event = data.get("webhookEvent", "")
        if "issue_" not in webhook_event:
            log.info(f"Skipping Jira event: {webhook_event}")
            return

        issue = data.get("issue", {})
        key = issue.get("key", "?")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        status = fields.get("status", {}).get("name", "?")
        user = data.get("user", {}).get("displayName", "Unknown")
        changelog = data.get("changelog", {})

        agent_emoji, agent_label = self._find_agent_by_summary(summary)

        changes = []
        if changelog:
            for item in changelog.get("items", []):
                field = item.get("field", "")
                from_str = item.get("fromString", "")
                to_str = item.get("toString", "")
                if field == "status":
                    changes.append(f"Status: {from_str} \u2192 {to_str}")
                elif field == "summary":
                    changes.append(f"Title updated")
                elif field == "assignee":
                    changes.append(f"Assignee: {from_str or 'unassigned'} \u2192 {to_str or 'unassigned'}")
                elif field in ("description", "labels", "priority"):
                    changes.append(f"{field} updated")
                else:
                    changes.append(f"{field} changed")

        change_text = "; ".join(changes[:3]) if changes else "Details updated"
        event_type = "\U0001f195 Created" if "created" in webhook_event else "\U0001f504 Updated"

        message = (
            f"{event_type} **{key}** by {user}\n"
            f"\U0001f4cc {summary}\n"
            f"\U0001f4ca {status}\n"
            f"\u270f\ufe0f {change_text}\n"
            f"\U0001f517 https://nomadforchrist.atlassian.net/browse/{key}"
        )

        if agent_emoji:
            self._notify_agent(agent_emoji, message)
        else:
            log.info(f"No agent found in Jira summary: {summary[:40]}")

    def _find_agent_by_summary(self, summary):
        """Find agent emoji in issue summary."""
        for emoji in ("\U0001f43b", "\U0001f3c0", "\U0001f9ee", "\U0001f3a4", "\U0001f3c3"):
            if emoji in summary:
                return emoji, AGENT_ROUTES[emoji][0]
        return None, None

    # ======================================================================
    #  TRELLO HANDLER
    # ======================================================================
    def _process_trello_update(self, data):
        action = data.get("action", {})
        action_type = action.get("type", "")

        if action_type not in ("commentCard", "updateCard"):
            log.info(f"Skipping Trello action type: {action_type}")
            return

        card = action.get("data", {}).get("card", {})
        card_id = card.get("id", "")
        card_name = card.get("name", "")

        if not card_id:
            return

        agent_emoji = self._find_agent_for_trello_card(card_id)
        if not agent_emoji:
            log.info(f"No agent assigned to Trello card: {card_name[:40]}")
            return

        member = action.get("memberCreator", {}).get("fullName", "Unknown")
        message = f"\U0001f4cb **{card_name}** updated by {member}"

        if action_type == "commentCard":
            comment = action.get("data", {}).get("text", "")
            message += f"\n\U0001f4ac Comment: {comment[:500]}"
        else:
            old = action.get("data", {}).get("old", {})
            new_vals = action.get("data", {}).get("new", {})
            changes = []
            for field in ("desc", "due", "name", "idList"):
                if field in old:
                    old_v = str(old[field])[:30]
                    new_v = str(new_vals.get(field, "?"))[:30]
                    changes.append(f"{field}: {old_v} \u2192 {new_v}")
            if changes:
                message += f"\n\u270f\ufe0f Changed: {'; '.join(changes[:3])}"

        message += f"\n\U0001f517 https://trello.com/c/{card_id[:8]}"
        self._notify_agent(agent_emoji, message)

    def _find_agent_for_trello_card(self, card_id):
        """Fetch Trello card labels to find agent."""
        url = (f"https://api.trello.com/1/cards/{card_id}"
               f"?fields=name&labels=true&key={TRELLO_KEY}&token={TRELLO_TOKEN}")
        try:
            req = Request(url)
            resp = urlopen(req, timeout=10)
            card_data = json.loads(resp.read())
            if not card_data.get("labels"):
                return None
            for label in card_data.get("labels", []):
                name = label.get("name", "")
                if name in LABEL_TO_AGENT:
                    return LABEL_TO_AGENT[name]
        except Exception as e:
            log.error(f"Error fetching Trello card {card_id}: {e}")
        return None

    # ======================================================================
    #  NOTIFICATION ROUTING
    # ======================================================================
    def _notify_agent(self, agent_emoji, message):
        if agent_emoji not in AGENT_ROUTES:
            log.warning(f"No route for emoji {agent_emoji}")
            return

        agent_label, route = AGENT_ROUTES[agent_emoji]
        log.info(f"Notifying {agent_label}: {message[:80]}...")

        if route == "docker_exec":
            msg_escaped = message.replace("'", "'\\''")
            os.system(f"echo '{msg_escaped}' | docker exec -i jim-maxxing pi 2>/dev/null")
            log.info("Sent to Jim via docker exec")
            return

        if route.startswith("telegram_bot:"):
            rest = route[len("telegram_bot:"):]
            if ":" in rest:
                last_colon = rest.rfind(":")
                bot_token = rest[:last_colon]
                chat_id = rest[last_colon + 1:]
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = json.dumps({
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }).encode()
                req = Request(url, data=payload, headers={"Content-Type": "application/json"})
                try:
                    urlopen(req, timeout=10)
                    log.info(f"Sent to {agent_label} via Telegram")
                except Exception as e:
                    log.error(f"Telegram error: {e}")
            return

        if route == "paperclip":
            msg_file = os.path.expanduser(
                f"~/.openclaw/workspace/{agent_label.lower().replace(' ', '-')}-notifications.md"
            )
            with open(msg_file, "a") as f:
                f.write(f"\n- {message}\n")
            log.info(f"Saved {agent_label} notification to {msg_file}")
            return

        if route.startswith("telegram:"):
            msg_file = os.path.expanduser("~/.openclaw/workspace/pam-notifications.md")
            with open(msg_file, "a") as f:
                f.write(f"\n- {message}\n")
            log.info(f"Saved Pam notification to {msg_file}")
            return

        log.info(f"No delivery method for {agent_label}")


def main():
    port = 7979
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    log.info(f"Webhook server listening on port {port}")
    log.info(f"Trello API proxy at http://127.0.0.1:{port}/trello-api/...")
    log.info(f"  GET  /trello-api/card/<shortLink>   — read card details")
    log.info(f"  PUT  /trello-api/move-card            — move card to list")
    log.info(f"  PUT  /trello-api/add-comment          — comment on card")
    log.info(f"  POST /trello-api/create-card          — create new card")
    log.info(f"  POST /trello-api/add-label            — add label to card")
    log.info(f"  POST /trello-api/list-labels          — list board labels")
    log.info(f"  POST /trello-api/list-lists           — list board lists")
    log.info(f"  POST /trello-api/creds/get              — retrieve a credential by name")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
