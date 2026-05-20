#!/usr/bin/env python3
"""
Trello Task Sync — Agent Task Management Protocol
Harness-agnostic: works with OpenClaw, Hermes, or any AI agent system.
MIT License.

Syncs a Trello board with a local SQLite database. Run on a schedule
or trigger it after any card operation.

Usage:
    python3 trello-sync.py [--init] [--report] [--dry-run]
"""

import os
import sys
import sqlite3
import argparse
import json
import subprocess
from datetime import datetime, date
from typing import Optional

# ── Config ──────────────────────────────────────────────────────────────────

TRELLO_API_KEY  = os.environ.get("TRELLO_API_KEY", "")
TRELLO_TOKEN    = os.environ.get("TRELLO_TOKEN", "")
TRELLO_BOARD_ID = os.environ.get("TRELLO_BOARD_ID", "")

TRELLO_BASE = "https://api.trello.com/1"
DB_PATH     = os.environ.get("TASKS_DB", os.path.join(os.environ["HOME"], "central-tasks", "tasks.db"))

COLUMNS = {"To-Do": "todo", "In Progress": "in_progress", "Blocked": "blocked", "Done": "done"}


# ── Trello API helpers ───────────────────────────────────────────────────────

def trello_get(path: str, params: dict = None) -> dict:
    import requests
    params = params or {}
    params["key"] = TRELLO_API_KEY
    params["token"] = TRELLO_TOKEN
    r = requests.get(f"{TRELLO_BASE}{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def trello_post(path: str, data: dict = None) -> dict:
    import requests
    data = data or {}
    data["key"] = TRELLO_API_KEY
    data["token"] = TRELLO_TOKEN
    r = requests.post(f"{TRELLO_BASE}{path}", json=data, timeout=15)
    r.raise_for_status()
    return r.json()


# ── Database ─────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            trello_card_id    TEXT UNIQUE NOT NULL,
            title             TEXT NOT NULL,
            description       TEXT,
            status            TEXT NOT NULL,
            column_name       TEXT NOT NULL,
            assigned_agent    TEXT,
            created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
            completed_at      DATETIME,
            blocked_reason    TEXT,
            completion_summary TEXT
        )
    """)
    conn.commit()
    conn.close()
    print(f"[OK] Database initialised at {DB_PATH}")


# ── Sync logic ───────────────────────────────────────────────────────────────

def fetch_board_state() -> tuple[list[dict], list[dict]]:
    """Returns (lists, cards)."""
    lists  = trello_get(f"/boards/{TRELLO_BOARD_ID}/lists")
    cards  = trello_get(f"/boards/{TRELLO_BOARD_ID}/cards")
    return lists, cards


def sync():
    conn = get_db()
    lists, cards = fetch_board_state()

    # Build list_id → column_name map
    list_map = {l["id"]: l["name"] for l in lists}

    created_today = 0
    active_count  = 0
    blocked_list  = []

    for card in cards:
        col_name = list_map.get(card["idList"], "")
        if col_name not in COLUMNS:
            continue  # skip columns not in our protocol

        status = COLUMNS[col_name]
        now    = datetime.utcnow().isoformat()

        row = conn.execute(
            "SELECT id, status FROM tasks WHERE trello_card_id = ?",
            (card["id"],)
        ).fetchone()

        if row is None:
            conn.execute("""
                INSERT INTO tasks (trello_card_id, title, description, status, column_name, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (card["id"], card["name"], card.get("desc", "") or "",
                  status, col_name, now, now))
            created_today += 1
            active_count  += 1
        else:
            conn.execute("""
                UPDATE tasks
                SET status = ?, column_name = ?, updated_at = ?,
                    completed_at = CASE WHEN ? = 'done' AND status != 'done' THEN ? ELSE completed_at END
                WHERE trello_card_id = ?
            """, (status, col_name, now,
                  status, now, card["id"]))
            if status != "done":
                active_count += 1

        # Check for blocked cards
        if col_name == "Blocked":
            # Fetch the last blocked comment from card actions
            try:
                actions = trello_get(f"/cards/{card['id']}/actions", {"filter": "comment"})
                blocked = next((a["data"]["text"] for a in reversed(actions)
                               if "🔴 BLOCKED" in (a["data"].get("text") or "")), None)
                if blocked:
                    conn.execute(
                        "UPDATE tasks SET blocked_reason = ? WHERE trello_card_id = ?",
                        (blocked, card["id"])
                    )
            except Exception:
                pass

        # Check for completion summary on Done cards
        if col_name == "Done":
            try:
                actions = trello_get(f"/cards/{card['id']}/actions", {"filter": "comment"})
                done = next((a["data"]["text"] for a in reversed(actions)
                             if "✅" in (a["data"].get("text") or "") or
                                "completed" in (a["data"].get("text") or "").lower()), None)
                if done:
                    conn.execute(
                        "UPDATE tasks SET completion_summary = ? WHERE trello_card_id = ?",
                        (done, card["id"])
                    )
            except Exception:
                pass

    conn.commit()
    conn.close()

    print(f"[SYNC] {created_today} new cards | {active_count} active tasks")
    return active_count, blocked_list


def report():
    conn = get_db()
    today = date.today().isoformat()

    rows = conn.execute(
        "SELECT * FROM tasks ORDER BY column_name, created_at"
    ).fetchall()

    lines = ["📋 *Daily Trello Report*", ""]

    # Created today
    created = [r for r in rows if str(r["created_at"]).startswith(today)]
    if created:
        lines.append(f"✅ *Created today:* {len(created)}")
        for r in created:
            lines.append(f"  • {r['title']} → {r['column_name']}")
        lines.append("")

    # Active
    active = [r for r in rows if r["status"] not in ("done",)]
    if active:
        lines.append(f"📌 *Active tasks ({len(active)}):*")
        for r in active:
            lines.append(f"  [{r['column_name']}] {r['title']}")
            if r.get("assigned_agent"):
                lines.append(f"    Assigned: {r['assigned_agent']}")
        lines.append("")

    # Blocked
    blocked = [r for r in rows if r["status"] == "blocked"]
    if blocked:
        lines.append(f"🔴 *Blocked ({len(blocked)}):*")
        for r in blocked:
            lines.append(f"  • {r['title']}")
            if r.get("blocked_reason"):
                lines.append(f"    {r['blocked_reason']}")
        lines.append("")

    # Done today
    done_today = [r for r in rows if r["status"] == "done" and r.get("completed_at", "").startswith(today)]
    if done_today:
        lines.append(f"🏁 *Done today:* {len(done_today)}")
        for r in done_today:
            lines.append(f"  • {r['title']}")
            if r.get("completion_summary"):
                lines.append(f"    {r['completion_summary']}")

    conn.close()
    print("\n".join(lines))
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def check_config():
    missing = [k for k in (TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID) if not k]
    if missing:
        print(f"[ERROR] Missing environment variables: {', '.join(missing)}", file=sys.stderr)
        print("Set TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID before running.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trello Task Sync")
    parser.add_argument("--init",   action="store_true", help="Initialise the database")
    parser.add_argument("--report", action="store_true", help="Print daily report")
    parser.add_argument("--dry-run", action="store_true", help="Read-only sync check")
    args = parser.parse_args()

    if args.init:
        init_db()
    elif args.report:
        check_config()
        report()
    else:
        check_config()
        if args.dry_run:
            print("[DRY RUN] Config OK, would sync.")
        else:
            sync()