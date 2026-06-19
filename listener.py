"""WS listener: subscribes to the Band room as a 5th agent and writes
final passport decisions into SQLite.

Run separately from app.py. Restart on crash.

Setup:
  1. Register a 5th agent 'passport_observer' on app.band.ai
  2. Add it to room 160a29dc-8f63-4236-adf8-aa0015d7e219
  3. Set PASSPORT_OBSERVER_ID and PASSPORT_OBSERVER_KEY in .env
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

BAND_WS_URL = os.environ.get("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
BAND_ROOM_ID = os.environ["BAND_ROOM_ID"]
OBSERVER_ID = os.environ.get("PASSPORT_OBSERVER_ID", "")
OBSERVER_KEY = os.environ.get("PASSPORT_OBSERVER_KEY", "")
DB_PATH = os.environ.get("DB_PATH", "passports.db")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("listener")

DECISION_RE = re.compile(r"Decision:\s*([a-z_]+)", re.IGNORECASE)
SCORE_RE = re.compile(r"[Tt]rust [Ss]core:?\s*(\d+)")
APPROVED_RE = re.compile(r"Approved [Pp]ermissions?:\s*\[([^\]]*)\]")
BLOCKED_RE = re.compile(r"Blocked [Pp]ermissions?:\s*\[([^\]]*)\]")
RATIONALE_RE = re.compile(r"Rationale:?\s*(.+?)(?:\n|$)", re.IGNORECASE | re.DOTALL)
PASSPORT_ID_RE = re.compile(r'"passport_id"\s*:\s*"([^"]+)"')
STATUS_RE = re.compile(r'"status"\s*:\s*"([^"]+)"')
REQUEST_ID_RE = re.compile(r"request_id=([0-9a-fA-F-]{36})")


def write_decision(request_id: str, passport: dict) -> None:
    status = passport.get("status", "unknown")
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "UPDATE passports SET status=?, result_json=?, decided_at=? WHERE request_id=?",
            (status, json.dumps(passport), now, request_id),
        )
    log.info("updated request_id=%s status=%s", request_id, status)


def extract_passport(text: str) -> dict | None:
    # JSON shape first
    if '"passport_id"' in text:
        for start in range(len(text)):
            if text[start] != "{":
                continue
            depth = 0
            for end in range(start, len(text)):
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                    if depth == 0:
                        chunk = text[start : end + 1]
                        if '"passport_id"' in chunk and '"status"' in chunk:
                            try:
                                return json.loads(chunk)
                            except json.JSONDecodeError:
                                continue
                        break
        return None
    # Natural-text shape: "Decision: X. Trust Score: N. Approved Permissions: [...]"
    m_dec = DECISION_RE.search(text)
    if not m_dec:
        return None
    decision = m_dec.group(1).strip().lower()
    m_score = SCORE_RE.search(text)
    m_app = APPROVED_RE.search(text)
    m_block = BLOCKED_RE.search(text)
    m_rat = RATIONALE_RE.search(text)
    approved = [p.strip().strip('"').strip("'") for p in (m_app.group(1).split(",") if m_app else []) if p.strip()]
    blocked = [p.strip().strip('"').strip("'") for p in (m_block.group(1).split(",") if m_block else []) if p.strip()]
    return {
        "passport_id": "pending-" + str(datetime.now(timezone.utc).timestamp()),
        "status": decision,
        "trust_score": int(m_score.group(1)) if m_score else None,
        "approved_permissions": approved,
        "blocked_permissions": blocked,
        "rationale": m_rat.group(1).strip() if m_rat else "",
    }


def handle_message(text: str) -> None:
    passport = extract_passport(text)
    if passport is None:
        return
    m = REQUEST_ID_RE.search(text)
    if not m:
        log.warning("passport found but no request_id in message; skipping")
        return
    write_decision(m.group(1), passport)


async def run() -> None:
    if not (OBSERVER_ID and OBSERVER_KEY):
        log.error(
            "PASSPORT_OBSERVER_ID and PASSPORT_OBSERVER_KEY must be set in .env. "
            "Register a 5th agent on app.band.ai first."
        )
        return

    from phoenix_channels_python_client import PHXChannelsClient  # type: ignore
    from phoenix_channels_python_client.phx_messages import ChannelMessage  # type: ignore

    async def on_room_message(msg: ChannelMessage) -> None:
        try:
            if msg.event != "message_created":
                return
            payload = msg.payload if isinstance(msg.payload, dict) else {}
            text = payload.get("content") or json.dumps(payload)
            if not isinstance(text, str):
                text = json.dumps(text)
            handle_message(text)
        except Exception:
            log.exception("error handling room message")

    topic = f"chat_room:{BAND_ROOM_ID}"
    async with PHXChannelsClient(
        BAND_WS_URL,
        OBSERVER_KEY,
        auto_reconnect=True,
    ) as client:
        if OBSERVER_ID:
            client.channel_socket_url += f"&agent_id={OBSERVER_ID}"
        await client.subscribe_to_topic(topic, on_room_message)
        log.info("listener started, subscribed to %s", topic)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
