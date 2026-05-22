#!/usr/bin/env python3
"""Synchronize Jason's Trello task board with the central task database."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


BOARD_ID = "Fi5EnmrN"
BOARD_URL = "https://trello.com/b/Fi5EnmrN/jasons-goal-board"
DB_PATH = "/home/ubuntu/central-tasks/tasks.db"
CREDS_PATH = "/home/ubuntu/.openclaw/trello_credentials.json"
ENV_PATHS = ("/home/ubuntu/.openclaw/.env", "/home/ubuntu/openclaw/.env")
ALLOWED_LISTS = ("To-Do", "In Progress", "Blocked", "Done")
AGENT_LABELS = {
    "pam": "Pam",
    "pam beesly": "Pam",
    "pam 🐻": "Pam",
    "concierge": "Pam",
    "michael": "Michael",
    "michael scott": "Michael",
    "michael 🎤": "Michael",
    "kevin": "Kevin",
    "kevin malone": "Kevin",
    "kevin 🧮": "Kevin",
    "dwight": "Dwight",
    "dwight schrute": "Dwight",
    "dwight 🏃": "Dwight",
    "milton": "Milton",
    "milton 🦞": "Milton",
    "orchestrator": "Milton",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_creds() -> tuple[str, str]:
    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    if api_key and token:
        return api_key, token
    if os.path.exists(CREDS_PATH):
        with open(CREDS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data["api_key"], data["token"]
    env = {}
    for path in ENV_PATHS:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip().strip("'\"")
    api_key = env.get("TRELLO_API_KEY")
    token = env.get("TRELLO_TOKEN")
    if api_key and token:
        return api_key, token
    raise RuntimeError("Trello credentials not found in env, credentials JSON, or OpenClaw .env")


def trello(path: str, method: str = "GET", data: dict[str, str] | None = None):
    api_key, token = load_creds()
    params = {"key": api_key, "token": token}
    url = "https://api.trello.com/1" + path
    encoded = None
    if method in {"GET", "DELETE"}:
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(params)
    else:
        payload = dict(params)
        if data:
            payload.update(data)
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(url, data=encoded, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body) if body else None


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trello_card_id TEXT UNIQUE,
            trello_short_link TEXT,
            trello_url TEXT,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            trello_list TEXT NOT NULL,
            assigned_agent TEXT,
            source TEXT NOT NULL DEFAULT 'trello',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            blocked_comment TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trello_sync_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trello_card_id TEXT,
            event_type TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def list_map() -> dict[str, str]:
    lists = trello(f"/boards/{BOARD_ID}/lists?fields=name,id")
    found = {item["name"]: item["id"] for item in lists if item["name"] in ALLOWED_LISTS}
    missing = [name for name in ALLOWED_LISTS if name not in found]
    if missing:
        raise RuntimeError(f"Missing required Trello lists: {', '.join(missing)}")
    return found


def choose_agent(card: dict) -> str:
    for label in card.get("labels") or []:
        name = (label.get("name") or "").strip().lower()
        if name in AGENT_LABELS:
            return AGENT_LABELS[name]
    text = f"{card.get('name', '')}\n{card.get('desc', '')}".lower()
    if "kevin" in text or "🧮" in text:
        return "Kevin"
    if "dwight" in text or "🏃" in text:
        return "Dwight"
    if "pam" in text or "🐻" in text:
        return "Pam"
    if "michael" in text or "🎤" in text:
        return "Michael"
    if "jim" in text or "🏀" in text:
        return "Dwight"
    if any(word in text for word in ("money", "account", "invoice", "tax", "budget", "finance", "grant", "credit", "refund", "subscription", "billing")):
        return "Kevin"
    if any(word in text for word in ("code", "program", "script", "qa", "test", "verify", "ops", "server", "deploy")):
        return "Dwight"
    if any(word in text for word in ("email", "calendar", "schedule", "admin", "document", "follow up")):
        return "Pam"
    if any(word in text for word in ("contract", "government", "veteran", "certification", "strategy", "research")):
        return "Michael"
    return "Milton"


def db_task(conn: sqlite3.Connection, card_id: str):
    return conn.execute("SELECT id, status, assigned_agent FROM tasks WHERE trello_card_id = ?", (card_id,)).fetchone()


def upsert_card(conn: sqlite3.Connection, card: dict, list_name: str, agent: str | None = None) -> None:
    now = utc_now()
    existing = db_task(conn, card["id"])
    assigned = agent or (existing[2] if existing else None) or choose_agent(card)
    completed_at = now if list_name == "Done" else None
    conn.execute(
        """
        INSERT INTO tasks (
            trello_card_id, trello_short_link, trello_url, title, description, status,
            trello_list, assigned_agent, created_at, updated_at, completed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trello_card_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            status = excluded.status,
            trello_list = excluded.trello_list,
            assigned_agent = excluded.assigned_agent,
            updated_at = excluded.updated_at,
            completed_at = CASE WHEN excluded.status = 'Done' THEN excluded.completed_at ELSE tasks.completed_at END
        """,
        (
            card["id"],
            card.get("shortLink"),
            card.get("url"),
            card.get("name", ""),
            card.get("desc", ""),
            list_name,
            list_name,
            assigned,
            now,
            now,
            completed_at,
        ),
    )
    conn.commit()


def add_comment(card_id: str, text: str) -> None:
    trello(f"/cards/{card_id}/actions/comments", method="POST", data={"text": text})


def move_card(card_id: str, list_id: str) -> None:
    trello(f"/cards/{card_id}", method="PUT", data={"idList": list_id})


def sync_once(dry_run: bool = False) -> None:
    lists = list_map()
    reverse = {v: k for k, v in lists.items()}
    cards = trello(f"/boards/{BOARD_ID}/cards?fields=name,desc,idList,url,shortLink,closed&labels=all")
    if dry_run:
        counts = {name: 0 for name in ALLOWED_LISTS}
        for card in cards:
            if card.get("closed"):
                continue
            list_name = reverse.get(card["idList"])
            if list_name:
                counts[list_name] += 1
        print(
            "trello-sync dry run: "
            + ", ".join(f"{name}={counts[name]}" for name in ALLOWED_LISTS)
            + f", total_open_allowed={sum(counts.values())}"
        )
        return
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    try:
        for card in cards:
            if card.get("closed"):
                continue
            if (card.get("name") or "").strip().lower().startswith(("📌 how to use this column", "how to use this column")):
                continue
            list_name = reverse.get(card["idList"])
            if not list_name:
                continue
            agent = choose_agent(card)
            was_known = db_task(conn, card["id"]) is not None
            upsert_card(conn, card, list_name, agent)
            if list_name == "To-Do":
                prefix = "Registered new Trello task" if not was_known else "Re-queued Trello task"
                add_comment(
                    card["id"],
                    f"{prefix} in central task database. Assigned agent: {agent}. Awaiting agent claim.",
                )
                conn.execute(
                    "INSERT INTO trello_sync_events (trello_card_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
                    (card["id"], "todo_registered", f"Assigned to {agent}; dispatcher will notify agent", utc_now()),
                )
                conn.commit()
            elif list_name == "Blocked":
                actions = trello(f"/cards/{card['id']}/actions?filter=commentCard&limit=10")
                blocked = next((a.get("data", {}).get("text", "") for a in actions if "🔴 BLOCKED" in a.get("data", {}).get("text", "")), None)
                if not blocked:
                    blocked = (
                        "🔴 BLOCKED\n"
                        "Reason: Existing Blocked card did not include the required blocked details.\n"
                        "Needed to Unblock: Assigned agent must inspect the task and replace this with the specific blocker.\n"
                        f"Who needs to act: {agent}\n"
                        "Estimated resolution time: Once the assigned agent reviews the card.\n"
                        "Workaround (if any): Keep the card in Blocked until the specific blocker is documented."
                    )
                    add_comment(card["id"], blocked)
                if blocked:
                    conn.execute(
                        "UPDATE tasks SET blocked_comment = ?, updated_at = ? WHERE trello_card_id = ?",
                        (blocked, utc_now(), card["id"]),
                    )
                    conn.commit()
    finally:
        conn.close()


def daily_report() -> str:
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created = conn.execute(
        "SELECT title, status, assigned_agent, trello_url FROM tasks WHERE substr(created_at, 1, 10) = ? ORDER BY created_at",
        (today,),
    ).fetchall()
    active = conn.execute(
        "SELECT title, status, assigned_agent, trello_url FROM tasks WHERE status != 'Done' ORDER BY status, updated_at DESC"
    ).fetchall()
    blocked = conn.execute(
        "SELECT title, assigned_agent, COALESCE(blocked_comment, '') FROM tasks WHERE status = 'Blocked' ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    lines = [f"Daily Trello Report — {today}", "", "Tasks created today:"]
    lines.extend([f"- [{t}]({u or BOARD_URL}) — {s} — {a or 'unassigned'}" for t, s, a, u in created] or ["- None"])
    lines.extend(["", "Active tasks:"])
    lines.extend([f"- [{t}]({u or BOARD_URL}) — {s} — {a or 'unassigned'}" for t, s, a, u in active] or ["- None"])
    lines.extend(["", "Blocked tasks:"])
    lines.extend([f"- {t} | {a or 'unassigned'}\n{c or 'No blocked comment found'}" for t, a, c in blocked] or ["- None"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Validate Trello access and report card counts without writing")
    args = parser.parse_args()
    if args.dry_run:
        sync_once(dry_run=True)
        return 0
    if args.report:
        sync_once()
        print(daily_report())
    else:
        sync_once()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"trello-sync failed: {exc}", file=sys.stderr)
        time.sleep(1)
        raise
