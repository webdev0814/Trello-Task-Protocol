#!/usr/bin/env python3
"""Dispatch labeled Trello tasks to the assigned agent.

This is the active layer above trello-sync.py. Trello remains the source of
truth; this script only records dispatch state so a polling timer can notify
agents idempotently and escalate stale cards.
"""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


BOARD_ID = "Fi5EnmrN"
BOARD_URL = "https://trello.com/b/Fi5EnmrN/jasons-goal-board"
DB_PATH = "/home/ubuntu/central-tasks/tasks.db"
CREDS_PATH = "/home/ubuntu/.openclaw/trello_credentials.json"
ENV_PATHS = ("/home/ubuntu/.openclaw/.env", "/home/ubuntu/openclaw/.env")
SCRIPT_DIR = Path("/home/ubuntu/central-tasks/scripts")
ALLOWED_LISTS = ("To-Do", "In Progress", "Blocked", "Done")
WATCH_LISTS = ("To-Do", "In Progress")
CLAIM_RENOTIFY_SECONDS = 5 * 60
ESCALATE_UNCLAIMED_SECONDS = 15 * 60
IN_PROGRESS_STALE_SECONDS = 60 * 60
CLAIM_COMMENT = "Starting work"


AGENT_LABELS = {
    "jason": None,
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


def unix_now() -> int:
    return int(time.time())


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
        CREATE TABLE IF NOT EXISTS trello_dispatch_state (
            trello_card_id TEXT PRIMARY KEY,
            assigned_agent TEXT NOT NULL,
            last_list TEXT NOT NULL,
            last_activity TEXT,
            last_action_id TEXT,
            notified_at INTEGER,
            claimed_at INTEGER,
            escalated_at INTEGER,
            dispatch_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
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
    existing = [row[1] for row in conn.execute("PRAGMA table_info(trello_dispatch_state)").fetchall()]
    if "last_action_id" not in existing:
        conn.execute("ALTER TABLE trello_dispatch_state ADD COLUMN last_action_id TEXT")
    if "claimed_at" not in existing:
        conn.execute("ALTER TABLE trello_dispatch_state ADD COLUMN claimed_at INTEGER")
    conn.commit()


def list_map() -> dict[str, str]:
    lists = trello(f"/boards/{BOARD_ID}/lists?fields=name,id")
    found = {item["name"]: item["id"] for item in lists if item["name"] in ALLOWED_LISTS}
    missing = [name for name in ALLOWED_LISTS if name not in found]
    if missing:
        raise RuntimeError(f"Missing required Trello lists: {', '.join(missing)}")
    return found


def label_agent(card: dict) -> str | None:
    labels = card.get("labels") or []
    for label in labels:
        name = (label.get("name") or "").strip().lower()
        if name == "jason":
            return None
        if name in AGENT_LABELS:
            return AGENT_LABELS[name]
    return None


def is_instruction_card(card: dict) -> bool:
    name = (card.get("name") or "").strip().lower()
    return name.startswith("📌 how to use this column") or name.startswith("how to use this column")


def choose_agent(card: dict) -> str:
    labels = card.get("labels") or []
    if any((label.get("name") or "").strip().lower() == "jason" for label in labels):
        return "Jason"
    labeled = label_agent(card)
    if labeled:
        return labeled
    text = f"{card.get('name', '')}\n{card.get('desc', '')}".lower()
    if "kevin" in text or "🧮" in text:
        return "Kevin"
    if "dwight" in text or "🏃" in text:
        return "Dwight"
    if "pam" in text or "🐻" in text:
        return "Pam"
    if "michael" in text or "🎤" in text:
        return "Michael"
    if any(word in text for word in ("money", "account", "invoice", "tax", "budget", "finance", "grant", "credit", "refund", "subscription", "billing")):
        return "Kevin"
    if any(word in text for word in ("code", "program", "script", "qa", "test", "verify", "ops", "server", "deploy")):
        return "Dwight"
    if any(word in text for word in ("email", "calendar", "schedule", "admin", "document", "follow up", "travel")):
        return "Pam"
    if any(word in text for word in ("contract", "government", "veteran", "certification", "strategy", "research", "project", "timeline")):
        return "Michael"
    return "Milton"


def upsert_task(conn: sqlite3.Connection, card: dict, list_name: str, agent: str) -> None:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO tasks (
            trello_card_id, trello_short_link, trello_url, title, description,
            status, trello_list, assigned_agent, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(trello_card_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            status = excluded.status,
            trello_list = excluded.trello_list,
            assigned_agent = excluded.assigned_agent,
            updated_at = excluded.updated_at
        """,
        (
            card["id"],
            card.get("shortLink"),
            card.get("url"),
            card.get("name", ""),
            card.get("desc", ""),
            list_name,
            list_name,
            agent,
            now,
            now,
        ),
    )


def add_event(conn: sqlite3.Connection, card_id: str, event_type: str, detail: str) -> None:
    conn.execute(
        "INSERT INTO trello_sync_events (trello_card_id, event_type, detail, created_at) VALUES (?, ?, ?, ?)",
        (card_id, event_type, detail, utc_now()),
    )


def trello_comment(card_id: str, text: str) -> None:
    trello(f"/cards/{card_id}/actions/comments", method="POST", data={"text": text})


def move_card(card_id: str, list_id: str) -> None:
    trello(f"/cards/{card_id}", method="PUT", data={"idList": list_id})


def card_actions(card_id: str) -> list[dict]:
    actions = trello(
        f"/cards/{card_id}/actions?filter=commentCard,updateCard:idList&limit=10&fields=id,type,date,data"
    )
    return actions or []


def latest_action_id(actions: list[dict]) -> str | None:
    return actions[0].get("id") if actions else None


def has_start_comment(actions: list[dict]) -> bool:
    for action in actions:
        if action.get("type") != "commentCard":
            continue
        text = ((action.get("data") or {}).get("text") or "").strip().lower()
        if text.startswith(CLAIM_COMMENT.lower()) or "starting work" in text:
            return True
    return False


def shell(args: list[str], timeout: int = 30) -> tuple[int, str]:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode, proc.stdout[-2000:]


def agent_prompt(card: dict, list_name: str, agent: str, reason: str) -> str:
    return (
        f"Trello task assigned to {agent}.\n\n"
        f"Card: {card.get('name', '')}\n"
        f"List: {list_name}\n"
        f"URL: {card.get('url', BOARD_URL)}\n"
        f"Reason: {reason}\n\n"
        "Required protocol:\n"
        "1. Open/review the Trello card.\n"
        "2. If it is in To-Do, add the exact starting comment 'Starting work' and move it to In Progress.\n"
        "3. Work the task immediately.\n"
        "4. If blocked, add the exact BLOCKED comment format and move it to Blocked.\n"
        "5. If complete, add a short completion summary and move it to Done.\n"
        "6. Do not create duplicate cards for this same work.\n\n"
        f"Description:\n{card.get('desc') or '(no description)'}"
    )


def notify_pam(card: dict, list_name: str, reason: str) -> tuple[bool, str]:
    prompt = agent_prompt(card, list_name, "Pam", reason)
    notice = Path("/home/ubuntu/.openclaw/agents/concierge/workspace/TASK_NOTIFICATION.md")
    trigger = Path("/home/ubuntu/.openclaw/agents/concierge/workspace/_TASK_TRIGGER_.md")
    notice.write_text(prompt + "\n", encoding="utf-8")
    trigger.write_text(f"{card['id']}|{card.get('name','')}|{unix_now()}\n", encoding="utf-8")
    subprocess.Popen(
        ["openclaw", "agent", "--agent", "concierge", "--message", prompt, "--thinking", "low", "--timeout", "1800"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True, "Pam agent turn started asynchronously"


def notify_milton(card: dict, list_name: str, reason: str) -> tuple[bool, str]:
    prompt = agent_prompt(card, list_name, "Milton", reason)
    subprocess.Popen(
        ["openclaw", "system", "event", "--mode", "now", "--text", prompt, "--timeout", "30000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return True, "Milton system event queued asynchronously"


def notify_hermes(agent: str, card: dict, list_name: str, reason: str) -> tuple[bool, str]:
    profile = agent.lower()
    prompt = agent_prompt(card, list_name, agent, reason)
    log_path = f"/tmp/trello-dispatcher-{profile}.log"
    remote_file = f"~/.hermes/profiles/{shlex.quote(profile)}/tasks/trello-{shlex.quote(card['id'])}.md"
    remote = (
        "set -eu; "
        f"mkdir -p ~/.hermes/profiles/{shlex.quote(profile)}/tasks; "
        f"cat > {remote_file}; "
        "nohup bash -lc "
        + shlex.quote(
            f"HERMES_PROFILE={profile} hermes chat --provider deepseek --model deepseek-v4-flash -q \"$(cat {remote_file})\" --source trello-dispatcher --yolo >> {log_path} 2>&1"
        )
        + " </dev/null >/dev/null 2>&1 &"
    )
    ssh = [
        "ssh",
        "-q",
        "-i",
        "/home/ubuntu/.ssh/oci_hermes_id_rsa",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "ConnectTimeout=8",
        "ubuntu@143.47.103.144",
        remote,
    ]
    proc = subprocess.run(ssh, input=prompt, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    return proc.returncode == 0, proc.stdout[-2000:]


def notify_agent(agent: str, card: dict, list_name: str, reason: str) -> tuple[bool, str]:
    if agent == "Jason":
        return False, "Jason-labeled cards are intentionally ignored by agents"
    if agent == "Pam":
        return notify_pam(card, list_name, reason)
    if agent == "Milton":
        return notify_milton(card, list_name, reason)
    if agent in {"Michael", "Kevin", "Dwight"}:
        return notify_hermes(agent, card, list_name, reason)
    return False, f"No notifier configured for {agent}"


def should_notify(state, list_name: str, date_last_activity: str | None, action_id: str | None) -> tuple[bool, str]:
    now = unix_now()
    if state is None:
        return True, "new labeled/assigned card"
    _, _, last_list, last_activity, last_action_id, notified_at, claimed_at, escalated_at, dispatch_count, _ = state
    notified_at = notified_at or 0
    if last_list != list_name:
        return True, f"card moved from {last_list} to {list_name}"
    if list_name == "To-Do" and now - notified_at >= CLAIM_RENOTIFY_SECONDS:
        return True, "To-Do card still unclaimed"
    if list_name == "In Progress" and now - notified_at >= IN_PROGRESS_STALE_SECONDS:
        return True, "In Progress card needs progress check"
    return False, "already dispatched"


def maybe_escalate(conn: sqlite3.Connection, card: dict, list_name: str, agent: str, state) -> None:
    if list_name != "To-Do" or agent == "Milton" or state is None:
        return
    now = unix_now()
    notified_at = state[5] or now
    claimed_at = state[6] or 0
    escalated_at = state[7] or 0
    if claimed_at:
        return
    if now - notified_at < ESCALATE_UNCLAIMED_SECONDS or now - escalated_at < ESCALATE_UNCLAIMED_SECONDS:
        return
    ok, out = notify_milton(card, list_name, f"{agent} has not claimed this To-Do card within 15 minutes")
    if ok:
        trello_comment(card["id"], f"Watchdog escalation: {agent} has not claimed this To-Do card. Milton has been notified.")
        conn.execute(
            "UPDATE trello_dispatch_state SET escalated_at = ?, updated_at = ? WHERE trello_card_id = ?",
            (now, utc_now(), card["id"]),
        )
        add_event(conn, card["id"], "watchdog_escalated", f"Escalated unclaimed card for {agent} to Milton")
    else:
        add_event(conn, card["id"], "watchdog_escalation_failed", out)


def dispatch_once(dry_run: bool = False) -> int:
    lists = list_map()
    reverse = {v: k for k, v in lists.items()}
    cards = trello(
        f"/boards/{BOARD_ID}/cards?fields=name,desc,idList,url,shortLink,closed,dateLastActivity&labels=all"
    )
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    dispatched = 0
    try:
        for card in cards:
            if card.get("closed"):
                continue
            if is_instruction_card(card):
                continue
            list_name = reverse.get(card["idList"])
            if list_name not in WATCH_LISTS:
                continue
            agent = choose_agent(card)
            if agent == "Jason":
                add_event(conn, card["id"], "ignored_jason_labeled_card", "Card labeled Jason is reserved for the human and skipped by agents")
                continue
            upsert_task(conn, card, list_name, agent)
            actions = card_actions(card["id"])
            action_id = latest_action_id(actions)
            claimed_at = unix_now() if list_name == "In Progress" or has_start_comment(actions) else None
            state = conn.execute(
                "SELECT trello_card_id, assigned_agent, last_list, last_activity, last_action_id, notified_at, claimed_at, escalated_at, dispatch_count, updated_at "
                "FROM trello_dispatch_state WHERE trello_card_id = ?",
                (card["id"],),
            ).fetchone()
            notify, reason = should_notify(state, list_name, card.get("dateLastActivity"), action_id)
            if notify:
                if dry_run:
                    print(f"Would notify {agent}: {card.get('name')} ({reason})")
                    continue
                ok, out = notify_agent(agent, card, list_name, reason)
                if ok:
                    dispatched += 1
                    if list_name == "To-Do":
                        trello_comment(card["id"], CLAIM_COMMENT)
                        move_card(card["id"], lists["In Progress"])
                        list_name = "In Progress"
                        claimed_at = unix_now()
                        conn.execute(
                            "UPDATE tasks SET status = ?, trello_list = ?, updated_at = ? WHERE trello_card_id = ?",
                            (list_name, list_name, utc_now(), card["id"]),
                        )
                    trello_comment(card["id"], f"Dispatcher notified {agent}. Reason: {reason}.")
                    updated_actions = card_actions(card["id"])
                    action_id = latest_action_id(updated_actions) or action_id
                    conn.execute(
                        """
                        INSERT INTO trello_dispatch_state (
                            trello_card_id, assigned_agent, last_list, last_activity, last_action_id,
                            notified_at, claimed_at, escalated_at, dispatch_count, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 1, ?)
                        ON CONFLICT(trello_card_id) DO UPDATE SET
                            assigned_agent = excluded.assigned_agent,
                            last_list = excluded.last_list,
                            last_activity = excluded.last_activity,
                            last_action_id = excluded.last_action_id,
                            notified_at = excluded.notified_at,
                            claimed_at = COALESCE(excluded.claimed_at, trello_dispatch_state.claimed_at),
                            dispatch_count = trello_dispatch_state.dispatch_count + 1,
                            updated_at = excluded.updated_at
                        """,
                        (card["id"], agent, list_name, card.get("dateLastActivity"), action_id, unix_now(), claimed_at, utc_now()),
                    )
                    add_event(conn, card["id"], "agent_notified", f"{agent}: {reason}")
                else:
                    add_event(conn, card["id"], "agent_notify_failed", f"{agent}: {out}")
            elif state and (action_id != state[4] or (claimed_at and not state[6])):
                conn.execute(
                    "UPDATE trello_dispatch_state SET last_list = ?, last_activity = ?, last_action_id = ?, claimed_at = COALESCE(claimed_at, ?), updated_at = ? WHERE trello_card_id = ?",
                    (list_name, card.get("dateLastActivity"), action_id, claimed_at, utc_now(), card["id"]),
                )
            maybe_escalate(conn, card, list_name, agent, state)
        conn.commit()
    finally:
        conn.close()
    return dispatched


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    count = dispatch_once(dry_run=dry_run)
    if not dry_run:
        print(f"trello-dispatcher notified {count} agent(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
